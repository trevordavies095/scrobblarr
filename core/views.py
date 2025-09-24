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


def index(request):
    """
    Home page view for Scrobblarr.
    """
    return HttpResponse("Welcome to Scrobblarr - Your Last.fm Analytics Dashboard")


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