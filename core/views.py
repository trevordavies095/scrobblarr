"""
Core views for Scrobblarr application including health checks and monitoring.
"""
import logging
import requests
import time
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.db import connection
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from music.models import Artist, Album, Track, Scrobble


logger = logging.getLogger('core')


def _format_relative_time(timestamp):
    """
    Format a timestamp as relative time (e.g., "2 hours ago").
    """
    now = timezone.now()
    diff = now - timestamp

    if diff.days > 0:
        if diff.days == 1:
            return "1 day ago"
        return f"{diff.days} days ago"

    hours = diff.seconds // 3600
    if hours > 0:
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"

    minutes = (diff.seconds // 60) % 60
    if minutes > 0:
        if minutes == 1:
            return "1 minute ago"
        return f"{minutes} minutes ago"

    return "Just now"


def index(request):
    """
    Enhanced home page view for Scrobblarr with comprehensive dashboard data.
    """
    from core.utils.stats import DashboardStats

    logger.info("Loading dashboard for user", extra={
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    try:
        # Initialize stats calculator
        stats_calculator = DashboardStats()

        # Get comprehensive dashboard data
        dashboard_data = stats_calculator.get_comprehensive_dashboard_data()

        # Get recent tracks (last 10) with optimized query
        recent_tracks_query = Scrobble.objects.select_related(
            'track', 'track__artist', 'track__album'
        ).order_by('-timestamp')[:10]

        # Format recent tracks for display with enhanced data
        recent_tracks_formatted = []
        for scrobble in recent_tracks_query:
            track_data = {
                'track_name': scrobble.track.name,
                'track_id': scrobble.track.id,
                'artist_name': scrobble.track.artist.name,
                'artist_id': scrobble.track.artist.id,
                'album_name': scrobble.track.album.name if scrobble.track.album else None,
                'album_id': scrobble.track.album.id if scrobble.track.album else None,
                'timestamp': scrobble.timestamp,
                'relative_time': _format_relative_time(scrobble.timestamp),
                'duration': scrobble.track.get_duration_formatted() if scrobble.track.duration else None,
                'play_count': scrobble.track.get_scrobble_count() if hasattr(scrobble.track, 'play_count') else None
            }
            recent_tracks_formatted.append(track_data)

        # Calculate enhanced statistics
        basic_counts = dashboard_data['basic_counts']
        listening_streak = dashboard_data['listening_streak']
        listening_time = dashboard_data['listening_time']
        top_items = dashboard_data['top_items']
        recent_activity = dashboard_data['recent_activity']
        sync_status = dashboard_data['sync_status']

        # Create enhanced stats with additional context
        enhanced_stats = {
            # Basic counts
            'total_scrobbles': basic_counts['total_scrobbles'],
            'unique_artists': basic_counts['unique_artists'],
            'unique_albums': basic_counts['unique_albums'],
            'unique_tracks': basic_counts['unique_tracks'],

            # Listening patterns
            'current_streak': listening_streak['current_streak'],
            'longest_streak': listening_streak['longest_streak'],
            'last_scrobble_date': listening_streak['last_scrobble_date'],

            # Time-based stats
            'estimated_listening_hours': round(listening_time['estimated_total_hours'], 1),
            'estimated_listening_days': round(listening_time['estimated_total_days'], 1),
            'average_track_duration': round(listening_time['average_track_duration'] / 60, 1) if listening_time['average_track_duration'] > 0 else None,

            # Activity stats
            'scrobbles_last_7_days': recent_activity['scrobbles_7_days'],
            'scrobbles_last_30_days': recent_activity['scrobbles_30_days'],
            'daily_average_7_days': round(recent_activity['daily_average_7_days'], 1),
            'daily_average_30_days': round(recent_activity['daily_average_30_days'], 1),

            # Top items
            'top_artist': top_items['top_artist'],
            'top_album': top_items['top_album'],
            'top_track': top_items['top_track'],
        }

        # Calculate change indicators for recent activity
        scrobble_change = None
        if recent_activity['scrobbles_7_days'] > 0 and recent_activity['scrobbles_30_days'] > recent_activity['scrobbles_7_days']:
            # Calculate weekly trend
            prev_week_estimate = (recent_activity['scrobbles_30_days'] - recent_activity['scrobbles_7_days']) / 3  # Rough weekly average
            if prev_week_estimate > 0:
                change_pct = ((recent_activity['scrobbles_7_days'] - prev_week_estimate) / prev_week_estimate) * 100
                direction = 'up' if change_pct > 0 else 'down'
                scrobble_change = {
                    'direction': direction,
                    'percentage': abs(change_pct),
                    'text': f"{'↑' if direction == 'up' else '↓'} {abs(change_pct):.1f}% vs last week"
                }

        enhanced_stats['scrobble_change'] = scrobble_change

        # Context for template
        context = {
            'stats': enhanced_stats,
            'recent_tracks': recent_tracks_formatted,
            'sync_status': sync_status,
            'dashboard_data': dashboard_data,  # Full data for advanced components
            'breadcrumbs': [],  # Homepage doesn't need breadcrumbs
        }

        # Log performance
        load_time = (timezone.now() - start_time).total_seconds()
        logger.info("Dashboard loaded successfully", extra={
            'load_time_seconds': load_time,
            'scrobble_count': enhanced_stats['total_scrobbles'],
            'recent_tracks_count': len(recent_tracks_formatted)
        })

    except Exception as e:
        logger.error("Error fetching enhanced dashboard data", exc_info=True)

        # Fallback to basic dashboard
        context = {
            'stats': {
                'total_scrobbles': 0,
                'unique_artists': 0,
                'unique_albums': 0,
                'unique_tracks': 0,
            },
            'recent_tracks': [],
            'sync_status': {
                'status': 'error',
                'last_sync': None,
                'error_message': 'Failed to load dashboard data'
            },
            'dashboard_data': None,
            'breadcrumbs': [],  # Homepage doesn't need breadcrumbs
        }

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'stats':
            return render(request, 'core/partials/dashboard_stats.html', context)
        elif partial == 'recent':
            return render(request, 'core/partials/recent_tracks.html', context)
        elif partial == 'sync':
            return render(request, 'core/partials/sync_status.html', context)

    return render(request, 'core/index.html', context)


def recent_tracks(request):
    """
    Recent tracks page with pagination, search, and filtering capabilities.
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.db.models import Q
    from datetime import datetime

    logger.info("Loading recent tracks page", extra={
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    # Get query parameters
    search_query = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    per_page = request.GET.get('per_page', '50')
    page = request.GET.get('page', '1')
    export_format = request.GET.get('export', '').strip()

    # Validate per_page parameter
    try:
        per_page = int(per_page)
        if per_page not in [25, 50, 100]:
            per_page = 50
    except (ValueError, TypeError):
        per_page = 50

    try:
        # Base queryset with optimized joins
        queryset = Scrobble.objects.select_related(
            'track', 'track__artist', 'track__album'
        ).order_by('-timestamp')

        # Apply search filter
        if search_query:
            queryset = queryset.filter(
                Q(track__name__icontains=search_query) |
                Q(track__artist__name__icontains=search_query) |
                Q(track__album__name__icontains=search_query)
            )

        # Apply date range filters
        if date_from:
            try:
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__gte=date_from_parsed)
            except ValueError:
                logger.warning(f"Invalid date_from format: {date_from}")

        if date_to:
            try:
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__lte=date_to_parsed)
            except ValueError:
                logger.warning(f"Invalid date_to format: {date_to}")

        # Handle export functionality
        if export_format == 'csv':
            logger.info("Exporting recent tracks to CSV", extra={
                'search_query': search_query,
                'date_from': date_from,
                'date_to': date_to,
                'total_count': queryset.count()
            })
            return _export_recent_tracks_csv(queryset[:10000])  # Limit export to 10k tracks

        # Pagination
        paginator = Paginator(queryset, per_page)

        try:
            scrobbles_page = paginator.page(page)
        except PageNotAnInteger:
            scrobbles_page = paginator.page(1)
        except EmptyPage:
            scrobbles_page = paginator.page(paginator.num_pages)

        # Format scrobbles for display
        scrobbles_formatted = []
        for scrobble in scrobbles_page:
            track_data = {
                'id': scrobble.id,
                'track_id': scrobble.track.id,
                'artist_id': scrobble.track.artist.id,
                'album_id': scrobble.track.album.id if scrobble.track.album else None,
                'track_name': scrobble.track.name,
                'artist_name': scrobble.track.artist.name,
                'album_name': scrobble.track.album.name if scrobble.track.album else '',
                'timestamp': scrobble.timestamp,
                'relative_time': _format_relative_time(scrobble.timestamp),
                'duration': scrobble.track.get_duration_formatted() if scrobble.track.duration else None,
            }
            scrobbles_formatted.append(track_data)

        # Pagination info
        pagination_info = {
            'current_page': scrobbles_page.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'per_page': per_page,
            'has_previous': scrobbles_page.has_previous(),
            'has_next': scrobbles_page.has_next(),
            'previous_page': scrobbles_page.previous_page_number() if scrobbles_page.has_previous() else None,
            'next_page': scrobbles_page.next_page_number() if scrobbles_page.has_next() else None,
            'start_index': scrobbles_page.start_index(),
            'end_index': scrobbles_page.end_index(),
        }

        # Generate page range for pagination (show 5 pages around current)
        page_range_start = max(1, scrobbles_page.number - 2)
        page_range_end = min(paginator.num_pages + 1, scrobbles_page.number + 3)
        pagination_info['page_range'] = range(page_range_start, page_range_end)

        context = {
            'scrobbles': scrobbles_formatted,
            'pagination': pagination_info,
            'search_query': search_query,
            'date_from': date_from,
            'date_to': date_to,
            'per_page': per_page,
            'breadcrumbs': [
                {'title': 'Home', 'url': '/'},
                {'title': 'Recent Tracks', 'url': None},
            ],
            'page_title': 'Recent Tracks',
            'error': None,
        }

        # Calculate performance metrics
        load_time = (timezone.now() - start_time).total_seconds()
        logger.info("Recent tracks page loaded", extra={
            'load_time_seconds': load_time,
            'total_scrobbles': paginator.count,
            'current_page': scrobbles_page.number,
            'per_page': per_page,
            'search_query': search_query,
            'has_filters': bool(search_query or date_from or date_to)
        })

    except Exception as e:
        logger.error("Error loading recent tracks page", exc_info=True)

        # Fallback context for error states
        context = {
            'scrobbles': [],
            'pagination': {
                'current_page': 1,
                'total_pages': 0,
                'total_count': 0,
                'per_page': per_page,
                'has_previous': False,
                'has_next': False,
                'page_range': [],
            },
            'search_query': search_query,
            'date_from': date_from,
            'date_to': date_to,
            'per_page': per_page,
            'breadcrumbs': [
                {'title': 'Home', 'url': '/'},
                {'title': 'Recent Tracks', 'url': None},
            ],
            'page_title': 'Recent Tracks',
            'error': 'Failed to load recent tracks. Please try again.',
        }

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'list':
            return render(request, 'core/partials/recent_tracks_list.html', context)
        elif partial == 'pagination':
            return render(request, 'core/partials/recent_tracks_pagination.html', context)

    return render(request, 'core/recent_tracks.html', context)


def _export_recent_tracks_csv(queryset):
    """
    Export recent tracks to CSV format.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="recent_tracks_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Track', 'Artist', 'Album', 'Relative Time'])

    for scrobble in queryset:
        writer.writerow([
            scrobble.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            scrobble.track.name,
            scrobble.track.artist.name,
            scrobble.track.album.name if scrobble.track.album else '',
            _format_relative_time(scrobble.timestamp)
        ])

    return response


def _export_top_artists_csv(artists_data, period_display):
    """
    Export top artists to CSV format.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="top_artists_{period_display.lower().replace(" ", "_")}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Rank', 'Artist', 'Scrobbles', 'Percentage', 'First Scrobble', 'Last Scrobble'])

    for artist in artists_data:
        writer.writerow([
            artist['rank'],
            artist['name'],
            artist['scrobble_count'],
            f"{artist['percentage']}%",
            artist.get('first_scrobble', ''),
            artist.get('last_scrobble', '')
        ])

    return response


def top_artists(request):
    """
    Top artists page with time period selector and dynamic filtering.
    """
    from datetime import datetime, timedelta
    from django.core.paginator import Paginator

    logger.info("Loading top artists page", extra={
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    # Get query parameters with defaults
    time_period = request.GET.get('period', 'all').strip().lower()
    limit = request.GET.get('limit', '25').strip()
    export_format = request.GET.get('export', '').strip()

    # Validate time period parameter
    valid_periods = ['7d', '30d', '90d', '180d', '365d', 'all']
    if time_period not in valid_periods:
        time_period = 'all'

    # Validate limit parameter
    try:
        limit = int(limit)
        if limit not in [10, 25, 50, 100]:
            limit = 25
    except (ValueError, TypeError):
        limit = 25

    try:
        # Build API request to existing stats endpoint
        api_url = f"http://127.0.0.1:8000/api/top-artists/"
        api_params = {
            'limit': limit,
        }

        # Add time period if not all-time
        if time_period != 'all':
            api_params['period'] = time_period

        # Make API request with timeout
        api_response = requests.get(api_url, params=api_params, timeout=10)

        if api_response.status_code == 200:
            api_data = api_response.json()

            # Extract artists and metadata
            artists_data = api_data.get('results', [])
            total_scrobbles = api_data.get('total_scrobbles', 0)
            period_display = api_data.get('period_display', 'All Time')

            # Format artists for template display
            formatted_artists = []
            max_scrobbles = max([artist.get('scrobble_count', 0) for artist in artists_data]) if artists_data else 1

            for rank, artist in enumerate(artists_data, 1):
                scrobble_count = artist.get('scrobble_count', 0)
                percentage = (scrobble_count / total_scrobbles * 100) if total_scrobbles > 0 else 0
                progress_width = (scrobble_count / max_scrobbles * 100) if max_scrobbles > 0 else 0

                formatted_artists.append({
                    'rank': rank,
                    'id': artist.get('id'),
                    'name': artist.get('name', 'Unknown Artist'),
                    'mbid': artist.get('mbid'),
                    'scrobble_count': scrobble_count,
                    'percentage': round(percentage, 2),
                    'progress_width': round(progress_width, 1),
                    'first_scrobble': artist.get('first_scrobble'),
                    'last_scrobble': artist.get('last_scrobble'),
                })
        else:
            # API error fallback
            logger.error(f"Stats API error: {api_response.status_code}")
            formatted_artists = []
            total_scrobbles = 0
            period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

    except requests.RequestException as e:
        logger.error("Failed to fetch top artists from API", exc_info=True)
        # Fallback to empty state
        formatted_artists = []
        total_scrobbles = 0
        period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

    except Exception as e:
        logger.error("Error loading top artists page", exc_info=True)
        # Fallback to empty state
        formatted_artists = []
        total_scrobbles = 0
        period_display = 'All Time'

    # Handle CSV export
    if export_format == 'csv' and formatted_artists:
        logger.info("Exporting top artists to CSV", extra={
            'period': time_period,
            'limit': limit,
            'artist_count': len(formatted_artists)
        })
        return _export_top_artists_csv(formatted_artists, period_display)

    # Build context for template
    context = {
        'artists': formatted_artists,
        'total_artists': len(formatted_artists),
        'total_scrobbles': total_scrobbles,
        'period_display': period_display,
        'selected_period': time_period,
        'selected_limit': limit,
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Top Artists', 'url': None},
        ],
        'page_title': 'Top Artists',
        'has_data': len(formatted_artists) > 0,
        'error': None,
        'period_options': [
            {'value': '7d', 'label': '7 days', 'active': time_period == '7d'},
            {'value': '30d', 'label': '30 days', 'active': time_period == '30d'},
            {'value': '90d', 'label': '90 days', 'active': time_period == '90d'},
            {'value': '180d', 'label': '180 days', 'active': time_period == '180d'},
            {'value': '365d', 'label': '1 year', 'active': time_period == '365d'},
            {'value': 'all', 'label': 'All Time', 'active': time_period == 'all'},
        ],
        'limit_options': [
            {'value': 10, 'label': '10', 'active': limit == 10},
            {'value': 25, 'label': '25', 'active': limit == 25},
            {'value': 50, 'label': '50', 'active': limit == 50},
            {'value': 100, 'label': '100', 'active': limit == 100},
        ],
    }

    # Log performance
    load_time = (timezone.now() - start_time).total_seconds()
    logger.info("Top artists page loaded", extra={
        'load_time_seconds': load_time,
        'period': time_period,
        'limit': limit,
        'artist_count': len(formatted_artists),
        'total_scrobbles': total_scrobbles
    })

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'list':
            return render(request, 'core/partials/top_artists_list.html', context)
        elif partial == 'filters':
            return render(request, 'core/partials/top_artists_filters.html', context)

    return render(request, 'core/top_artists.html', context)


def _export_top_albums_csv(albums_data, period_display):
    """
    Export top albums to CSV format.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="top_albums_{period_display.lower().replace(" ", "_")}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Rank', 'Album', 'Artist', 'Scrobbles', 'Percentage', 'First Scrobble', 'Last Scrobble'])

    for album in albums_data:
        writer.writerow([
            album['rank'],
            album['name'],
            album['artist_name'],
            album['scrobble_count'],
            f"{album['percentage']}%",
            album.get('first_scrobble', ''),
            album.get('last_scrobble', '')
        ])

    return response


def _export_top_tracks_csv(tracks_data, period_display):
    """
    Export top tracks to CSV format.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="top_tracks_{period_display.lower().replace(" ", "_")}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Rank', 'Track', 'Artist', 'Album', 'Scrobbles', 'Percentage', 'First Scrobble', 'Last Scrobble'])

    for track in tracks_data:
        writer.writerow([
            track['rank'],
            track['name'],
            track['artist_name'],
            track['album_name'] or 'Unknown Album',
            track['scrobble_count'],
            f"{track['percentage']}%",
            track.get('first_scrobble', ''),
            track.get('last_scrobble', '')
        ])

    return response


def top_albums(request):
    """
    Top albums page with time period selector and dynamic filtering.
    """
    from datetime import datetime, timedelta
    from django.core.paginator import Paginator

    logger.info("Loading top albums page", extra={
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    # Get query parameters with defaults
    time_period = request.GET.get('period', 'all').strip().lower()
    limit = request.GET.get('limit', '25').strip()
    export_format = request.GET.get('export', '').strip()

    # Validate time period parameter
    valid_periods = ['7d', '30d', '90d', '180d', '365d', 'all']
    if time_period not in valid_periods:
        time_period = 'all'

    # Validate limit parameter
    try:
        limit = int(limit)
        if limit not in [10, 25, 50, 100]:
            limit = 25
    except (ValueError, TypeError):
        limit = 25

    try:
        # Build API request to existing stats endpoint
        api_url = f"http://127.0.0.1:8000/api/top-albums/"
        api_params = {
            'limit': limit,
        }

        # Add time period if not all-time
        if time_period != 'all':
            api_params['period'] = time_period

        # Make API request with timeout
        api_response = requests.get(api_url, params=api_params, timeout=10)

        if api_response.status_code == 200:
            api_data = api_response.json()

            # Extract albums and metadata
            albums_data = api_data.get('results', [])
            total_scrobbles = api_data.get('total_scrobbles', 0)
            period_display = api_data.get('period_display', 'All Time')

            # Format albums for template display
            formatted_albums = []
            max_scrobbles = max([album.get('scrobble_count', 0) for album in albums_data]) if albums_data else 1

            for rank, album in enumerate(albums_data, 1):
                scrobble_count = album.get('scrobble_count', 0)
                percentage = (scrobble_count / total_scrobbles * 100) if total_scrobbles > 0 else 0
                progress_width = (scrobble_count / max_scrobbles * 100) if max_scrobbles > 0 else 0

                formatted_albums.append({
                    'rank': rank,
                    'id': album.get('id'),
                    'name': album.get('name', 'Unknown Album'),
                    'artist_name': album.get('artist', 'Unknown Artist'),
                    'artist_id': album.get('artist_id'),
                    'mbid': album.get('mbid'),
                    'scrobble_count': scrobble_count,
                    'percentage': round(percentage, 2),
                    'progress_width': round(progress_width, 1),
                    'first_scrobble': album.get('first_scrobble'),
                    'last_scrobble': album.get('last_scrobble'),
                })
        else:
            # API error fallback
            logger.error(f"Stats API error: {api_response.status_code}")
            formatted_albums = []
            total_scrobbles = 0
            period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

    except requests.RequestException as e:
        logger.error("Failed to fetch top albums from API", exc_info=True)
        # Fallback to empty state
        formatted_albums = []
        total_scrobbles = 0
        period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

    except Exception as e:
        logger.error("Error loading top albums page", exc_info=True)
        # Fallback to empty state
        formatted_albums = []
        total_scrobbles = 0
        period_display = 'All Time'

    # Handle CSV export
    if export_format == 'csv' and formatted_albums:
        logger.info("Exporting top albums to CSV", extra={
            'period': time_period,
            'limit': limit,
            'album_count': len(formatted_albums)
        })
        return _export_top_albums_csv(formatted_albums, period_display)

    # Build context for template
    context = {
        'albums': formatted_albums,
        'total_albums': len(formatted_albums),
        'total_scrobbles': total_scrobbles,
        'period_display': period_display,
        'selected_period': time_period,
        'selected_limit': limit,
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Top Albums', 'url': None},
        ],
        'page_title': 'Top Albums',
        'has_data': len(formatted_albums) > 0,
        'error': None,
        'period_options': [
            {'value': '7d', 'label': '7 days', 'active': time_period == '7d'},
            {'value': '30d', 'label': '30 days', 'active': time_period == '30d'},
            {'value': '90d', 'label': '90 days', 'active': time_period == '90d'},
            {'value': '180d', 'label': '180 days', 'active': time_period == '180d'},
            {'value': '365d', 'label': '1 year', 'active': time_period == '365d'},
            {'value': 'all', 'label': 'All Time', 'active': time_period == 'all'},
        ],
        'limit_options': [
            {'value': 10, 'label': '10', 'active': limit == 10},
            {'value': 25, 'label': '25', 'active': limit == 25},
            {'value': 50, 'label': '50', 'active': limit == 50},
            {'value': 100, 'label': '100', 'active': limit == 100},
        ],
    }

    # Log performance
    load_time = (timezone.now() - start_time).total_seconds()
    logger.info("Top albums page loaded", extra={
        'load_time_seconds': load_time,
        'period': time_period,
        'limit': limit,
        'album_count': len(formatted_albums),
        'total_scrobbles': total_scrobbles
    })

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'list':
            return render(request, 'core/partials/top_albums_list.html', context)
        elif partial == 'filters':
            return render(request, 'core/partials/top_albums_filters.html', context)

    return render(request, 'core/top_albums.html', context)


def top_tracks(request):
    """
    Top tracks page with time period filtering and CSV export (Story 24 implementation).
    """
    import requests  # Local import as backup
    start_time = timezone.now()

    # Extract and validate parameters
    time_period = request.GET.get('period', 'all').strip().lower()
    limit = request.GET.get('limit', '25').strip()
    export_format = request.GET.get('export', '').strip().lower()

    # Validate time period parameter
    valid_periods = ['7d', '30d', '90d', '180d', '365d', 'all']
    if time_period not in valid_periods:
        time_period = 'all'

    # Validate limit parameter
    try:
        limit = int(limit)
        if limit not in [10, 25, 50, 100]:
            limit = 25
    except (ValueError, TypeError):
        limit = 25

    logger.info("Loading top tracks page", extra={
        'period': time_period,
        'limit': limit,
        'export_format': export_format
    })

    try:
        # Build API request to existing stats endpoint
        api_url = f"http://127.0.0.1:8000/api/top-tracks/"
        api_params = {
            'limit': limit,
        }

        # Add time period if not all-time
        if time_period != 'all':
            api_params['period'] = time_period

        # Make API request with timeout
        api_response = requests.get(api_url, params=api_params, timeout=10)

        if api_response.status_code == 200:
            api_data = api_response.json()

            # Extract tracks and metadata
            tracks_data = api_data.get('results', [])
            total_scrobbles = api_data.get('total_scrobbles', 0)
            period_display = api_data.get('period_display', 'All Time')

            # Format tracks for template display
            formatted_tracks = []
            max_scrobbles = max([track.get('scrobble_count', 0) for track in tracks_data]) if tracks_data else 1

            for rank, track in enumerate(tracks_data, 1):
                scrobble_count = track.get('scrobble_count', 0)
                percentage = (scrobble_count / total_scrobbles * 100) if total_scrobbles > 0 else 0
                progress_width = (scrobble_count / max_scrobbles * 100) if max_scrobbles > 0 else 0

                formatted_tracks.append({
                    'rank': rank,
                    'id': track.get('id'),
                    'name': track.get('track', 'Unknown Track'),
                    'artist_name': track.get('artist', 'Unknown Artist'),
                    'artist_id': track.get('artist_id'),
                    'album_name': track.get('album', 'Unknown Album'),
                    'album_id': track.get('album_id'),
                    'mbid': track.get('mbid'),
                    'duration': track.get('duration_formatted'),  # Already formatted as MM:SS
                    'scrobble_count': scrobble_count,
                    'percentage': round(percentage, 2),
                    'progress_width': round(progress_width, 1),
                    'first_scrobble': track.get('first_scrobble'),
                    'last_scrobble': track.get('last_scrobble'),
                })
        else:
            # API error fallback
            logger.error(f"Stats API error: {api_response.status_code}")
            formatted_tracks = []
            total_scrobbles = 0
            period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

    except requests.RequestException as e:
        logger.error("Failed to fetch top tracks from API", exc_info=True)
        # Fallback to empty state
        formatted_tracks = []
        total_scrobbles = 0
        period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

    except Exception as e:
        logger.error("Error loading top tracks page", exc_info=True)
        # Fallback to empty state
        formatted_tracks = []
        total_scrobbles = 0
        period_display = 'All Time'

    # Handle CSV export
    if export_format == 'csv' and formatted_tracks:
        logger.info("Exporting top tracks to CSV", extra={
            'period': time_period,
            'limit': limit,
            'track_count': len(formatted_tracks)
        })
        return _export_top_tracks_csv(formatted_tracks, period_display)

    # Build context for template
    context = {
        'tracks': formatted_tracks,
        'total_tracks': len(formatted_tracks),
        'total_scrobbles': total_scrobbles,
        'period_display': period_display,
        'selected_period': time_period,
        'selected_limit': limit,
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Top Tracks', 'url': None},
        ],
        'page_title': 'Top Tracks',
        'has_data': len(formatted_tracks) > 0,
        'error': None,
        'period_options': [
            {'value': '7d', 'label': '7 days', 'active': time_period == '7d'},
            {'value': '30d', 'label': '30 days', 'active': time_period == '30d'},
            {'value': '90d', 'label': '90 days', 'active': time_period == '90d'},
            {'value': '180d', 'label': '180 days', 'active': time_period == '180d'},
            {'value': '365d', 'label': '1 year', 'active': time_period == '365d'},
            {'value': 'all', 'label': 'All Time', 'active': time_period == 'all'},
        ],
        'limit_options': [
            {'value': 10, 'label': '10', 'active': limit == 10},
            {'value': 25, 'label': '25', 'active': limit == 25},
            {'value': 50, 'label': '50', 'active': limit == 50},
            {'value': 100, 'label': '100', 'active': limit == 100},
        ],
    }

    # Log performance
    load_time = (timezone.now() - start_time).total_seconds()
    logger.info("Top tracks page loaded", extra={
        'load_time_seconds': load_time,
        'period': time_period,
        'limit': limit,
        'track_count': len(formatted_tracks),
        'total_scrobbles': total_scrobbles
    })

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'list':
            return render(request, 'core/partials/top_tracks_list.html', context)
        elif partial == 'filters':
            return render(request, 'core/partials/top_tracks_filters.html', context)

    return render(request, 'core/top_tracks.html', context)


def charts(request):
    """
    Charts and visualization page with interactive scrobbles over time visualization.
    Implements Story 25: Charts & Visualization Page requirements.
    """
    import requests
    import json

    logger.info("Loading charts page", extra={
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    # Get query parameters with defaults
    time_period = request.GET.get('period', 'all').strip().lower()
    granularity = request.GET.get('granularity', 'auto').strip().lower()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    # Validate time period parameter
    valid_periods = ['7d', '30d', '90d', '180d', '365d', 'all']
    if time_period not in valid_periods:
        time_period = 'all'

    # Validate granularity parameter
    valid_granularities = ['auto', 'daily', 'monthly', 'yearly']
    if granularity not in valid_granularities:
        granularity = 'auto'

    try:
        # Build API request to chart data endpoint
        api_url = f"http://127.0.0.1:8000/api/scrobbles/chart/"
        api_params = {}

        # Add time period or custom date range
        if date_from and date_to:
            # Custom date range mode
            api_params['date_from'] = date_from
            api_params['date_to'] = date_to
            period_display = f"{date_from} to {date_to}"
        elif time_period != 'all':
            # Time period mode
            api_params['period'] = time_period
            period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()
        else:
            period_display = 'All Time'

        # Add granularity if not auto
        if granularity != 'auto':
            api_params['granularity'] = granularity

        # Make API request with timeout
        api_response = requests.get(api_url, params=api_params, timeout=15)

        if api_response.status_code == 200:
            api_data = api_response.json()

            # Extract chart data from API response
            chart_points = api_data.get('data', [])
            total_scrobbles = api_data.get('total_scrobbles', 0)
            actual_granularity = api_data.get('granularity', 'daily')
            actual_period = api_data.get('period', period_display)

            # Format chart data for Chart.js
            chart_labels = [point.get('period', '') for point in chart_points]
            chart_values = [point.get('scrobble_count', 0) for point in chart_points]

            # Calculate some statistics for display
            max_scrobbles = max(chart_values) if chart_values else 0
            avg_scrobbles = round(sum(chart_values) / len(chart_values), 1) if chart_values else 0

            chart_success = True
            chart_error = None

        else:
            # API error fallback
            logger.error(f"Chart API error: {api_response.status_code}")
            chart_labels = []
            chart_values = []
            total_scrobbles = 0
            max_scrobbles = 0
            avg_scrobbles = 0
            actual_granularity = granularity if granularity != 'auto' else 'daily'
            actual_period = period_display
            chart_success = False
            chart_error = f"Failed to load chart data (HTTP {api_response.status_code})"

    except requests.RequestException as e:
        logger.error("Failed to fetch chart data from API", exc_info=True)
        # Fallback to empty state
        chart_labels = []
        chart_values = []
        total_scrobbles = 0
        max_scrobbles = 0
        avg_scrobbles = 0
        actual_granularity = granularity if granularity != 'auto' else 'daily'
        actual_period = period_display
        chart_success = False
        chart_error = "Unable to connect to chart data service"

    except Exception as e:
        logger.error("Error loading charts page", exc_info=True)
        # Fallback to empty state
        chart_labels = []
        chart_values = []
        total_scrobbles = 0
        max_scrobbles = 0
        avg_scrobbles = 0
        actual_granularity = 'daily'
        actual_period = 'All Time'
        chart_success = False
        chart_error = "An unexpected error occurred while loading chart data"

    # Build context for template
    chart_data_dict = {
        'labels': chart_labels,
        'values': chart_values,
        'success': chart_success,
        'error': chart_error,
    }

    context = {
        'chart_data': json.dumps(chart_data_dict),  # JSON string for JavaScript
        'chart_data_dict': chart_data_dict,  # Python dict for template conditionals
        'chart_stats': {
            'total_scrobbles': total_scrobbles,
            'max_scrobbles': max_scrobbles,
            'avg_scrobbles': avg_scrobbles,
            'data_points': len(chart_labels),
            'period_display': actual_period,
            'granularity': actual_granularity.title(),
        },
        'selected_period': time_period,
        'selected_granularity': granularity,
        'custom_date_from': date_from,
        'custom_date_to': date_to,
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Charts', 'url': None},
        ],
        'page_title': 'Charts & Visualizations',
        'period_options': [
            {'value': '7d', 'label': '7 days', 'active': time_period == '7d'},
            {'value': '30d', 'label': '30 days', 'active': time_period == '30d'},
            {'value': '90d', 'label': '90 days', 'active': time_period == '90d'},
            {'value': '180d', 'label': '180 days', 'active': time_period == '180d'},
            {'value': '365d', 'label': '1 year', 'active': time_period == '365d'},
            {'value': 'all', 'label': 'All Time', 'active': time_period == 'all'},
        ],
        'granularity_options': [
            {'value': 'auto', 'label': 'Auto', 'active': granularity == 'auto'},
            {'value': 'daily', 'label': 'Daily', 'active': granularity == 'daily'},
            {'value': 'monthly', 'label': 'Monthly', 'active': granularity == 'monthly'},
            {'value': 'yearly', 'label': 'Yearly', 'active': granularity == 'yearly'},
        ],
    }

    # Log performance
    load_time = (timezone.now() - start_time).total_seconds()
    logger.info("Charts page loaded", extra={
        'load_time_seconds': load_time,
        'period': time_period,
        'granularity': granularity,
        'total_scrobbles': total_scrobbles,
        'data_points': len(chart_labels),
        'custom_range': bool(date_from and date_to)
    })

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'chart':
            return render(request, 'core/partials/charts_container.html', context)
        elif partial == 'filters':
            return render(request, 'core/partials/charts_filters.html', context)

    return render(request, 'core/charts.html', context)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring system status.

    Returns:
        - status: overall system health status
        - timestamp: current server timestamp
        - database: database connectivity status
        - data_counts: basic data statistics
        - version: application version info
    """
    start_time = time.time()

    logger.info("Health check requested", extra={
        'remote_addr': request.META.get('REMOTE_ADDR'),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')
    })

    status_data = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'checks': {},
        'response_time_ms': 0
    }

    # Database connectivity check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        status_data['checks']['database'] = {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
        logger.debug("Database health check passed")

    except Exception as e:
        status_data['status'] = 'unhealthy'
        status_data['checks']['database'] = {
            'status': 'unhealthy',
            'message': f'Database connection failed: {str(e)}'
        }
        logger.error("Database health check failed", exc_info=True)

    # Data counts check
    try:
        counts = {
            'artists': Artist.objects.count(),
            'albums': Album.objects.count(),
            'tracks': Track.objects.count(),
            'scrobbles': Scrobble.objects.count()
        }

        status_data['checks']['data'] = {
            'status': 'healthy',
            'counts': counts
        }

        # Log data health metrics
        logger.info("Data health check completed", extra={
            'artist_count': counts['artists'],
            'album_count': counts['albums'],
            'track_count': counts['tracks'],
            'scrobble_count': counts['scrobbles']
        })

    except Exception as e:
        status_data['status'] = 'unhealthy'
        status_data['checks']['data'] = {
            'status': 'unhealthy',
            'message': f'Data count query failed: {str(e)}'
        }
        logger.error("Data health check failed", exc_info=True)

    # Recent activity check
    try:
        recent_cutoff = timezone.now() - timedelta(days=1)
        recent_scrobbles = Scrobble.objects.filter(timestamp__gte=recent_cutoff).count()

        status_data['checks']['activity'] = {
            'status': 'healthy',
            'recent_scrobbles_24h': recent_scrobbles
        }

        if recent_scrobbles == 0:
            logger.warning("No recent scrobbles found in the last 24 hours")

    except Exception as e:
        status_data['checks']['activity'] = {
            'status': 'unhealthy',
            'message': f'Recent activity check failed: {str(e)}'
        }
        logger.error("Activity health check failed", exc_info=True)

    # Configuration check
    try:
        config_issues = []

        # Check critical settings
        if not settings.SECRET_KEY or settings.SECRET_KEY == 'django-insecure-your-secret-key-here-change-in-production':
            config_issues.append('SECRET_KEY not properly configured')

        if settings.DEBUG and not settings.ALLOWED_HOSTS:
            config_issues.append('ALLOWED_HOSTS not configured for production')

        if config_issues:
            status_data['checks']['configuration'] = {
                'status': 'warning',
                'issues': config_issues
            }
            logger.warning("Configuration issues detected", extra={
                'issues': config_issues
            })
        else:
            status_data['checks']['configuration'] = {
                'status': 'healthy',
                'message': 'Configuration appears valid'
            }

    except Exception as e:
        status_data['checks']['configuration'] = {
            'status': 'unhealthy',
            'message': f'Configuration check failed: {str(e)}'
        }
        logger.error("Configuration health check failed", exc_info=True)

    # Calculate response time
    response_time = (time.time() - start_time) * 1000
    status_data['response_time_ms'] = round(response_time, 2)

    # Log slow health checks
    if response_time > 1000:  # Slower than 1 second
        logger.warning(f"Slow health check response: {response_time:.0f}ms")

    # Determine HTTP status code
    http_status = 200
    if status_data['status'] == 'unhealthy':
        http_status = 503
    elif any(check.get('status') == 'warning' for check in status_data['checks'].values()):
        http_status = 200  # Still return 200 for warnings

    logger.info(f"Health check completed", extra={
        'overall_status': status_data['status'],
        'response_time_ms': response_time,
        'http_status': http_status
    })

    return JsonResponse(status_data, status=http_status)


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check endpoint for container orchestration.

    Checks if the application is ready to serve traffic.
    """
    logger.info("Readiness check requested")

    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM django_migrations")
            migration_count = cursor.fetchone()[0]

        if migration_count == 0:
            logger.error("No migrations found - database not properly initialized")
            return JsonResponse({
                'status': 'not_ready',
                'message': 'Database not initialized'
            }, status=503)

        # Check that essential tables exist
        Artist.objects.exists()

        logger.info("Readiness check passed")
        return JsonResponse({
            'status': 'ready',
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        logger.error("Readiness check failed", exc_info=True)
        return JsonResponse({
            'status': 'not_ready',
            'message': str(e)
        }, status=503)


@api_view(['GET'])
@permission_classes([AllowAny])
def liveness_check(request):
    """
    Liveness check endpoint for container orchestration.

    Simple check to verify the application is running.
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': timezone.now().isoformat()
    })


def artist_detail(request, pk):
    """
    Artist detail page with comprehensive artist information.
    Implements Story 26: Artist Detail Page requirements.
    """
    import requests
    import json

    logger.info("Loading artist detail page", extra={
        'artist_id': pk,
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    # Get query parameters for filtering
    time_period = request.GET.get('period', 'all').strip().lower()
    tab = request.GET.get('tab', 'overview').strip().lower()

    # Validate time period parameter
    valid_periods = ['7d', '30d', '90d', '180d', '365d', 'all']
    if time_period not in valid_periods:
        time_period = 'all'

    # Validate tab parameter
    valid_tabs = ['overview', 'charts']
    if tab not in valid_tabs:
        tab = 'overview'

    try:
        # Build API request to artist detail endpoint
        api_url = f"http://127.0.0.1:8000/api/artists/{pk}/"
        api_params = {}

        # Add time period filtering if not all time
        if time_period != 'all':
            api_params['period'] = time_period

        # Make API request with timeout
        api_response = requests.get(api_url, params=api_params, timeout=15)

        if api_response.status_code == 200:
            api_data = api_response.json()

            # Extract artist data from API response
            artist_info = api_data.get('artist', {})
            top_albums = api_data.get('top_albums', [])
            top_tracks = api_data.get('top_tracks', [])
            chart_data_raw = api_data.get('chart_data', {})

            # Parse datetime strings back to datetime objects for template
            if artist_info.get('first_scrobbled'):
                try:
                    # Parse ISO datetime string back to datetime object
                    first_str = artist_info['first_scrobbled'].replace('Z', '+00:00')
                    artist_info['first_scrobbled'] = datetime.fromisoformat(first_str)
                except (ValueError, AttributeError):
                    artist_info['first_scrobbled'] = None

            if artist_info.get('last_scrobbled'):
                try:
                    # Parse ISO datetime string back to datetime object
                    last_str = artist_info['last_scrobbled'].replace('Z', '+00:00')
                    artist_info['last_scrobbled'] = datetime.fromisoformat(last_str)
                except (ValueError, AttributeError):
                    artist_info['last_scrobbled'] = None

            # Transform chart data from API format to Chart.js format
            chart_data_array = chart_data_raw.get('data', [])
            chart_labels = [item['period'] for item in chart_data_array]
            chart_values = [item['scrobble_count'] for item in chart_data_array]

            # Calculate time period display text
            period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

            artist_success = True
            artist_error = None

        elif api_response.status_code == 404:
            # Artist not found
            logger.warning(f"Artist not found: {pk}")
            artist_info = {}
            top_albums = []
            top_tracks = []
            chart_labels = []
            chart_values = []
            period_display = 'All Time'
            artist_success = False
            artist_error = "Artist not found"

        else:
            # API error fallback
            logger.error(f"Artist API error: {api_response.status_code}")
            artist_info = {}
            top_albums = []
            top_tracks = []
            chart_labels = []
            chart_values = []
            period_display = 'All Time'
            artist_success = False
            artist_error = f"Failed to load artist data (HTTP {api_response.status_code})"

    except requests.RequestException as e:
        logger.error("Failed to fetch artist data from API", exc_info=True)
        # Fallback to empty state
        artist_info = {}
        top_albums = []
        top_tracks = []
        chart_labels = []
        chart_values = []
        period_display = 'All Time'
        artist_success = False
        artist_error = "Unable to connect to artist data service"

    except Exception as e:
        logger.error("Error loading artist detail page", exc_info=True)
        # Fallback to empty state
        artist_info = {}
        top_albums = []
        top_tracks = []
        chart_labels = []
        chart_values = []
        period_display = 'All Time'
        artist_success = False
        artist_error = "An unexpected error occurred while loading artist data"

    # Build chart data for JavaScript
    chart_data_dict = {
        'labels': chart_labels,
        'values': chart_values,
        'success': artist_success and len(chart_labels) > 0,
        'error': artist_error if not artist_success else None,
    }

    # Build breadcrumb navigation
    breadcrumbs = [
        {'title': 'Home', 'url': '/'},
        {'title': 'Artists', 'url': '/top-artists/'},
    ]

    if artist_success and artist_info.get('name'):
        breadcrumbs.append({'title': artist_info['name'], 'url': None})
    else:
        breadcrumbs.append({'title': 'Artist Detail', 'url': None})

    context = {
        'artist_info': artist_info,
        'artist_success': artist_success,
        'artist_error': artist_error,
        'top_albums': top_albums[:10],  # Limit to top 10
        'top_tracks': top_tracks[:10],  # Limit to top 10
        'chart_data': json.dumps(chart_data_dict),  # JSON string for JavaScript
        'chart_data_dict': chart_data_dict,  # Python dict for template conditionals
        'selected_period': time_period,
        'selected_tab': tab,
        'breadcrumbs': breadcrumbs,
        'page_title': artist_info.get('name', 'Artist Detail'),
        'period_options': [
            {'value': '7d', 'label': '7 days', 'active': time_period == '7d'},
            {'value': '30d', 'label': '30 days', 'active': time_period == '30d'},
            {'value': '90d', 'label': '90 days', 'active': time_period == '90d'},
            {'value': '180d', 'label': '180 days', 'active': time_period == '180d'},
            {'value': '365d', 'label': '1 year', 'active': time_period == '365d'},
            {'value': 'all', 'label': 'All Time', 'active': time_period == 'all'},
        ],
        'tab_options': [
            {'value': 'overview', 'label': 'Overview', 'active': tab == 'overview'},
            {'value': 'charts', 'label': 'Charts', 'active': tab == 'charts'},
        ],
        'period_display': period_display,
    }

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'overview':
            return render(request, 'core/partials/artist_overview_content.html', context)
        elif partial == 'charts':
            return render(request, 'core/partials/artist_chart_container.html', context)
        elif partial == 'full':
            # Return the full dynamic content area (time period selector + tab content)
            return render(request, 'core/partials/artist_dynamic_content.html', context)

    return render(request, 'core/artist_detail.html', context)


def album_detail(request, pk):
    """
    Album detail page with comprehensive album information.
    Implements Story 27: Album Detail Page requirements.
    """
    import requests
    import json

    logger.info("Loading album detail page", extra={
        'album_id': pk,
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    # Get query parameters for filtering
    time_period = request.GET.get('period', 'all').strip().lower()
    tab = request.GET.get('tab', 'overview').strip().lower()

    # Validate time period parameter
    valid_periods = ['7d', '30d', '90d', '180d', '365d', 'all']
    if time_period not in valid_periods:
        time_period = 'all'

    # Validate tab parameter
    valid_tabs = ['overview', 'charts']
    if tab not in valid_tabs:
        tab = 'overview'

    try:
        # Build API request to album detail endpoint
        api_url = f"http://127.0.0.1:8000/api/albums/{pk}/"
        api_params = {}

        # Add time period filtering if not all time
        if time_period != 'all':
            api_params['period'] = time_period

        # Make API request with timeout
        api_response = requests.get(api_url, params=api_params, timeout=15)

        if api_response.status_code == 200:
            api_data = api_response.json()

            # Extract album data from API response
            album_info = api_data.get('album', {})
            tracks_list = api_data.get('tracks', [])
            chart_data_raw = api_data.get('chart_data', {})

            # Parse datetime strings back to datetime objects for template
            if album_info.get('first_scrobbled'):
                try:
                    # Parse ISO datetime string back to datetime object
                    first_str = album_info['first_scrobbled'].replace('Z', '+00:00')
                    album_info['first_scrobbled'] = datetime.fromisoformat(first_str)
                except (ValueError, AttributeError):
                    album_info['first_scrobbled'] = None

            if album_info.get('last_scrobbled'):
                try:
                    # Parse ISO datetime string back to datetime object
                    last_str = album_info['last_scrobbled'].replace('Z', '+00:00')
                    album_info['last_scrobbled'] = datetime.fromisoformat(last_str)
                except (ValueError, AttributeError):
                    album_info['last_scrobbled'] = None

            # Transform chart data from API format to Chart.js format
            chart_data_array = chart_data_raw.get('data', [])
            chart_labels = [item['period'] for item in chart_data_array]
            chart_values = [item['scrobble_count'] for item in chart_data_array]

            # Calculate time period display text
            period_display = time_period.replace('d', ' days').replace('all', 'All Time').title()

            album_success = True
            album_error = None

        elif api_response.status_code == 404:
            # Album not found
            logger.warning(f"Album not found: {pk}")
            album_info = {}
            tracks_list = []
            chart_labels = []
            chart_values = []
            period_display = 'All Time'
            album_success = False
            album_error = "Album not found"

        else:
            # API error fallback
            logger.error(f"Album API error: {api_response.status_code}")
            album_info = {}
            tracks_list = []
            chart_labels = []
            chart_values = []
            period_display = 'All Time'
            album_success = False
            album_error = f"Failed to load album data (HTTP {api_response.status_code})"

    except requests.RequestException as e:
        logger.error("Failed to fetch album data from API", exc_info=True)
        # Fallback to empty state
        album_info = {}
        tracks_list = []
        chart_labels = []
        chart_values = []
        period_display = 'All Time'
        album_success = False
        album_error = "Unable to connect to album data service"

    except Exception as e:
        logger.error("Error loading album detail page", exc_info=True)
        # Fallback to empty state
        album_info = {}
        tracks_list = []
        chart_labels = []
        chart_values = []
        period_display = 'All Time'
        album_success = False
        album_error = "An unexpected error occurred while loading album data"

    # Build chart data for JavaScript
    chart_data_dict = {
        'labels': chart_labels,
        'values': chart_values,
        'success': album_success and len(chart_labels) > 0,
        'error': album_error if not album_success else None,
    }

    # Build breadcrumb navigation
    breadcrumbs = [
        {'title': 'Home', 'url': '/'},
        {'title': 'Artists', 'url': '/top-artists/'},
    ]

    if album_success and album_info.get('artist_name'):
        artist_id = album_info.get('artist_id')
        if artist_id:
            breadcrumbs.append({
                'title': album_info['artist_name'],
                'url': f'/artists/{artist_id}/'
            })
        else:
            breadcrumbs.append({'title': album_info['artist_name'], 'url': None})

    if album_success and album_info.get('name'):
        breadcrumbs.append({'title': album_info['name'], 'url': None})
    else:
        breadcrumbs.append({'title': 'Album Detail', 'url': None})

    context = {
        'album_info': album_info,
        'album_success': album_success,
        'album_error': album_error,
        'tracks_list': tracks_list,
        'chart_data': json.dumps(chart_data_dict),  # JSON string for JavaScript
        'chart_data_dict': chart_data_dict,  # Python dict for template conditionals
        'selected_period': time_period,
        'selected_tab': tab,
        'breadcrumbs': breadcrumbs,
        'page_title': f"{album_info.get('name', 'Album Detail')} by {album_info.get('artist_name', 'Unknown Artist')}" if album_success else 'Album Detail',
        'period_options': [
            {'value': '7d', 'label': '7 days', 'active': time_period == '7d'},
            {'value': '30d', 'label': '30 days', 'active': time_period == '30d'},
            {'value': '90d', 'label': '90 days', 'active': time_period == '90d'},
            {'value': '180d', 'label': '180 days', 'active': time_period == '180d'},
            {'value': '365d', 'label': '1 year', 'active': time_period == '365d'},
            {'value': 'all', 'label': 'All Time', 'active': time_period == 'all'},
        ],
        'tab_options': [
            {'value': 'overview', 'label': 'Overview', 'active': tab == 'overview'},
            {'value': 'charts', 'label': 'Charts', 'active': tab == 'charts'},
        ],
        'period_display': period_display,
    }

    # Handle partial template requests for htmx updates
    partial = request.GET.get('partial')
    if partial:
        if partial == 'overview':
            return render(request, 'core/partials/album_overview_content.html', context)
        elif partial == 'charts':
            return render(request, 'core/partials/album_chart_container.html', context)
        elif partial == 'full':
            # Return the full dynamic content area (time period selector + tab content)
            return render(request, 'core/partials/album_dynamic_content.html', context)

    return render(request, 'core/album_detail.html', context)


def search(request):
    """
    Global search functionality across artists, albums, and tracks.
    Implements Story 28: Search Functionality requirements.
    """
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    logger.info("Loading search page", extra={
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    search_query = request.GET.get('q', '').strip()
    category = request.GET.get('category', 'all').strip().lower()
    limit_per_category = 20

    valid_categories = ['all', 'artists', 'albums', 'tracks']
    if category not in valid_categories:
        category = 'all'

    artists_results = []
    albums_results = []
    tracks_results = []
    total_results = 0

    if search_query:
        try:
            if category in ['all', 'artists']:
                artists_query = Artist.objects.filter(
                    name__icontains=search_query
                ).annotate(
                    scrobble_count=Count('tracks__scrobbles')
                ).order_by('-scrobble_count', 'name')[:limit_per_category]

                artists_results = [
                    {
                        'id': artist.id,
                        'name': artist.name,
                        'mbid': artist.mbid,
                        'scrobble_count': artist.scrobble_count,
                        'url': f'/artists/{artist.id}/'
                    }
                    for artist in artists_query
                ]

            if category in ['all', 'albums']:
                albums_query = Album.objects.filter(
                    Q(name__icontains=search_query) |
                    Q(artist__name__icontains=search_query)
                ).select_related('artist').annotate(
                    scrobble_count=Count('tracks__scrobbles')
                ).order_by('-scrobble_count', 'name')[:limit_per_category]

                albums_results = [
                    {
                        'id': album.id,
                        'name': album.name,
                        'artist_name': album.artist.name,
                        'artist_id': album.artist.id,
                        'mbid': album.mbid,
                        'scrobble_count': album.scrobble_count,
                        'url': f'/albums/{album.id}/'
                    }
                    for album in albums_query
                ]

            if category in ['all', 'tracks']:
                tracks_query = Track.objects.filter(
                    Q(name__icontains=search_query) |
                    Q(artist__name__icontains=search_query) |
                    Q(album__name__icontains=search_query)
                ).select_related('artist', 'album').annotate(
                    scrobble_count=Count('scrobbles')
                ).order_by('-scrobble_count', 'name')[:limit_per_category]

                tracks_results = [
                    {
                        'id': track.id,
                        'name': track.name,
                        'artist_name': track.artist.name,
                        'artist_id': track.artist.id,
                        'album_name': track.album.name if track.album else 'Unknown Album',
                        'album_id': track.album.id if track.album else None,
                        'duration': track.get_duration_formatted() if track.duration else None,
                        'scrobble_count': track.scrobble_count,
                    }
                    for track in tracks_query
                ]

            total_results = len(artists_results) + len(albums_results) + len(tracks_results)

            if search_query:
                recent_searches = request.session.get('recent_searches', [])
                if search_query not in recent_searches:
                    recent_searches.insert(0, search_query)
                    recent_searches = recent_searches[:5]
                    request.session['recent_searches'] = recent_searches

            logger.info("Search completed", extra={
                'search_query': search_query,
                'category': category,
                'artists_found': len(artists_results),
                'albums_found': len(albums_results),
                'tracks_found': len(tracks_results),
                'total_results': total_results
            })

        except Exception as e:
            logger.error("Error performing search", exc_info=True)
            artists_results = []
            albums_results = []
            tracks_results = []
            total_results = 0

    recent_searches = request.session.get('recent_searches', [])

    context = {
        'search_query': search_query,
        'selected_category': category,
        'artists_results': artists_results,
        'albums_results': albums_results,
        'tracks_results': tracks_results,
        'total_results': total_results,
        'recent_searches': recent_searches,
        'has_results': total_results > 0,
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Search', 'url': None},
        ],
        'page_title': f'Search Results for "{search_query}"' if search_query else 'Search',
        'category_options': [
            {'value': 'all', 'label': 'All', 'active': category == 'all'},
            {'value': 'artists', 'label': 'Artists', 'active': category == 'artists'},
            {'value': 'albums', 'label': 'Albums', 'active': category == 'albums'},
            {'value': 'tracks', 'label': 'Tracks', 'active': category == 'tracks'},
        ],
    }

    load_time = (timezone.now() - start_time).total_seconds()
    logger.info("Search page loaded", extra={
        'load_time_seconds': load_time,
        'search_query': search_query,
        'total_results': total_results
    })

    partial = request.GET.get('partial')
    if partial:
        if partial == 'artists':
            return render(request, 'core/partials/search_artists_list.html', context)
        elif partial == 'albums':
            return render(request, 'core/partials/search_albums_list.html', context)
        elif partial == 'tracks':
            return render(request, 'core/partials/search_tracks_list.html', context)
        elif partial == 'results':
            return render(request, 'core/partials/search_all_results.html', context)

    return render(request, 'core/search_results.html', context)


def settings_view(request):
    """
    Settings page for Last.fm configuration and other app settings.
    Implements Story 31: Last.fm API Configuration requirements.
    """
    from music.lastfm import LastFmClient
    from music.lastfm.config import get_lastfm_config
    from music.models import SyncStatus
    from core.forms import LastFmSettingsForm
    import os

    logger.info("Loading settings page", extra={
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'remote_addr': request.META.get('REMOTE_ADDR')
    })

    start_time = timezone.now()

    lastfm_config = get_lastfm_config()
    connection_test_result = None
    form_success = False

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'test_connection':
            logger.info("Testing Last.fm connection")

            try:
                with LastFmClient(lastfm_config) as client:
                    success, error_message = client.test_connection()

                if success:
                    connection_test_result = {
                        'success': True,
                        'message': f"Successfully connected to Last.fm as {lastfm_config.username}"
                    }
                    logger.info("Last.fm connection test passed")
                else:
                    connection_test_result = {
                        'success': False,
                        'message': error_message or "Connection test failed"
                    }
                    logger.warning(f"Last.fm connection test failed: {error_message}")

            except Exception as e:
                logger.error("Error during Last.fm connection test", exc_info=True)
                connection_test_result = {
                    'success': False,
                    'message': f"Connection test error: {str(e)}"
                }

            initial_data = {
                'lastfm_username': lastfm_config.username,
                'sync_frequency': lastfm_config.sync_frequency,
            }
            form = LastFmSettingsForm(initial=initial_data)

        elif action == 'save_settings':
            logger.info("Saving Last.fm settings")
            form = LastFmSettingsForm(request.POST)

            if form.is_valid():
                username = form.cleaned_data['lastfm_username']
                sync_frequency = form.cleaned_data['sync_frequency']

                logger.info(
                    "Updating settings (Note: Settings are environment-based, update .env file)",
                    extra={
                        'username': username,
                        'sync_frequency': sync_frequency
                    }
                )

                form_success = True

                logger.info("Settings update noted - user should update .env file")

            else:
                logger.warning("Settings form validation failed", extra={
                    'errors': form.errors.as_json()
                })
    else:
        initial_data = {
            'lastfm_username': lastfm_config.username,
            'sync_frequency': lastfm_config.sync_frequency,
        }
        form = LastFmSettingsForm(initial=initial_data)

    config_status = lastfm_config.get_status()

    try:
        sync_status = SyncStatus.objects.first()
        if not sync_status:
            sync_status = SyncStatus.objects.create()
    except Exception as e:
        logger.error("Error fetching sync status", exc_info=True)
        sync_status = None

    context = {
        'form': form,
        'config_status': config_status,
        'connection_test_result': connection_test_result,
        'form_success': form_success,
        'sync_status': sync_status,
        'api_key_configured': config_status['has_api_key'],
        'api_secret_configured': config_status['has_api_secret'],
        'username_configured': config_status['has_username'],
        'is_fully_configured': config_status['configured'],
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Settings', 'url': None},
        ],
        'page_title': 'Settings',
    }

    load_time = (timezone.now() - start_time).total_seconds()
    logger.info("Settings page loaded", extra={
        'load_time_seconds': load_time,
        'configured': config_status['configured']
    })

    partial = request.GET.get('partial')
    if partial:
        if partial == 'lastfm':
            return render(request, 'core/partials/lastfm_settings.html', context)

    return render(request, 'core/settings.html', context)