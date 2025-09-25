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
    Recent tracks page (placeholder for Phase 3).
    """
    context = {
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Recent Tracks'},
        ]
    }
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Recent Tracks',
        'description': 'View your complete recent listening history with filtering and search capabilities.',
        **context
    })


def top_artists(request):
    """
    Top artists page (placeholder for Phase 3).
    """
    context = {
        'breadcrumbs': [
            {'title': 'Home', 'url': '/'},
            {'title': 'Top Artists'},
        ]
    }
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Top Artists',
        'description': 'Discover your most played artists across different time periods.',
        **context
    })


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