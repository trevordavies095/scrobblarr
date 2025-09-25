"""
Core views for Scrobblarr application including health checks and monitoring.
"""
import logging
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
                'artist_name': scrobble.track.artist.name,
                'album_name': scrobble.track.album.name if scrobble.track.album else None,
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
    import requests
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


def top_albums(request):
    """
    Top albums page (placeholder for Phase 3).
    """
    context = {
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Top Albums'},
        ]
    }
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Top Albums',
        'description': 'Explore your favorite albums and their listening statistics.',
        **context
    })


def top_tracks(request):
    """
    Top tracks page (placeholder for Phase 3).
    """
    context = {
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Top Tracks'},
        ]
    }
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Top Tracks',
        'description': 'Identify your most played songs and track preferences.',
        **context
    })


def charts(request):
    """
    Charts and visualization page (placeholder for Phase 3).
    """
    context = {
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Charts'},
        ]
    }
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Charts & Analytics',
        'description': 'Visualize your listening patterns with interactive charts and analytics.',
        **context
    })


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