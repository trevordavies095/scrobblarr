"""
Statistics calculation utilities for dashboard and analytics.
"""
import logging
from datetime import datetime, timedelta
from django.db import models
from django.db.models import Count, Q, Max, Min, Avg
from django.utils import timezone
from django.core.cache import cache
from music.models import Artist, Album, Track, Scrobble, SyncStatus

logger = logging.getLogger('core.stats')


class DashboardStats:
    """
    Main class for calculating dashboard statistics with caching.
    """

    def __init__(self, cache_timeout=300):  # 5 minutes default cache
        self.cache_timeout = cache_timeout

    def get_basic_counts(self):
        """
        Get basic counts for all main entities.
        Cached for performance.
        """
        cache_key = 'dashboard_basic_counts'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data

        try:
            counts = {
                'total_scrobbles': Scrobble.objects.count(),
                'unique_artists': Artist.objects.count(),
                'unique_albums': Album.objects.count(),
                'unique_tracks': Track.objects.count(),
            }

            # Cache for 5 minutes
            cache.set(cache_key, counts, self.cache_timeout)
            logger.debug("Basic counts calculated and cached", extra=counts)
            return counts

        except Exception as e:
            logger.error("Error calculating basic counts", exc_info=True)
            return {
                'total_scrobbles': 0,
                'unique_artists': 0,
                'unique_albums': 0,
                'unique_tracks': 0,
            }

    def get_listening_streak(self):
        """
        Calculate current and longest listening streaks.
        A streak is consecutive days with at least one scrobble.
        """
        cache_key = 'dashboard_listening_streak'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data

        try:
            # Get all unique scrobble dates, ordered by date
            scrobble_dates = (
                Scrobble.objects.dates('timestamp', 'day', order='DESC')
            )

            if not scrobble_dates:
                return {
                    'current_streak': 0,
                    'longest_streak': 0,
                    'last_scrobble_date': None,
                    'streak_start_date': None
                }

            dates_list = list(scrobble_dates)
            today = timezone.now().date()

            # Calculate current streak
            current_streak = 0
            streak_start_date = None

            if dates_list and dates_list[0] >= today - timedelta(days=1):
                # Start counting from the most recent date
                current_streak = 1
                streak_start_date = dates_list[0]

                for i in range(1, len(dates_list)):
                    # Check if this date is consecutive to the previous
                    if dates_list[i] == dates_list[i-1] - timedelta(days=1):
                        current_streak += 1
                        streak_start_date = dates_list[i]
                    else:
                        break

            # Calculate longest streak
            longest_streak = 0
            temp_streak = 1

            for i in range(1, len(dates_list)):
                if dates_list[i-1] - dates_list[i] == timedelta(days=1):
                    temp_streak += 1
                else:
                    longest_streak = max(longest_streak, temp_streak)
                    temp_streak = 1

            longest_streak = max(longest_streak, temp_streak)

            result = {
                'current_streak': current_streak,
                'longest_streak': longest_streak,
                'last_scrobble_date': dates_list[0] if dates_list else None,
                'streak_start_date': streak_start_date
            }

            # Cache for 1 hour
            cache.set(cache_key, result, 3600)
            logger.debug("Listening streak calculated", extra=result)
            return result

        except Exception as e:
            logger.error("Error calculating listening streak", exc_info=True)
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'last_scrobble_date': None,
                'streak_start_date': None
            }

    def get_listening_time_estimates(self):
        """
        Calculate estimated total listening time and average track length.
        """
        cache_key = 'dashboard_listening_time'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data

        try:
            # Get average track duration from tracks with duration data
            track_stats = Track.objects.filter(duration__isnull=False).aggregate(
                avg_duration=Avg('duration'),
                total_tracks_with_duration=Count('id')
            )

            avg_duration = track_stats.get('avg_duration', 0) or 0
            total_scrobbles = Scrobble.objects.count()

            # If we don't have duration data, estimate with average song length (3.5 minutes)
            if avg_duration == 0:
                avg_duration = 210  # 3.5 minutes in seconds

            # Calculate estimated total listening time
            estimated_total_seconds = total_scrobbles * avg_duration
            estimated_total_hours = estimated_total_seconds / 3600
            estimated_total_days = estimated_total_hours / 24

            result = {
                'estimated_total_seconds': int(estimated_total_seconds),
                'estimated_total_hours': estimated_total_hours,
                'estimated_total_days': estimated_total_days,
                'average_track_duration': avg_duration,
                'tracks_with_duration': track_stats.get('total_tracks_with_duration', 0)
            }

            # Cache for 6 hours
            cache.set(cache_key, result, 21600)
            logger.debug("Listening time estimates calculated", extra=result)
            return result

        except Exception as e:
            logger.error("Error calculating listening time estimates", exc_info=True)
            return {
                'estimated_total_seconds': 0,
                'estimated_total_hours': 0,
                'estimated_total_days': 0,
                'average_track_duration': 0,
                'tracks_with_duration': 0
            }

    def get_top_items_summary(self):
        """
        Get top artist, album, and track for quick dashboard display.
        """
        cache_key = 'dashboard_top_items'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data

        try:
            # Top artist by scrobble count
            top_artist = (
                Artist.objects.annotate(
                    play_count=Count('tracks__scrobbles')
                )
                .filter(play_count__gt=0)
                .order_by('-play_count')
                .first()
            )

            # Top album by scrobble count
            top_album = (
                Album.objects.annotate(
                    play_count=Count('tracks__scrobbles')
                )
                .filter(play_count__gt=0)
                .order_by('-play_count')
                .select_related('artist')
                .first()
            )

            # Top track by scrobble count
            top_track = (
                Track.objects.annotate(
                    play_count=Count('scrobbles')
                )
                .filter(play_count__gt=0)
                .order_by('-play_count')
                .select_related('artist', 'album')
                .first()
            )

            result = {
                'top_artist': {
                    'name': top_artist.name if top_artist else None,
                    'play_count': getattr(top_artist, 'play_count', 0) if top_artist else 0
                },
                'top_album': {
                    'name': top_album.name if top_album else None,
                    'artist_name': top_album.artist.name if top_album else None,
                    'play_count': getattr(top_album, 'play_count', 0) if top_album else 0
                },
                'top_track': {
                    'name': top_track.name if top_track else None,
                    'artist_name': top_track.artist.name if top_track else None,
                    'album_name': top_track.album.name if top_track and top_track.album else None,
                    'play_count': getattr(top_track, 'play_count', 0) if top_track else 0
                }
            }

            # Cache for 1 hour
            cache.set(cache_key, result, 3600)
            logger.debug("Top items summary calculated")
            return result

        except Exception as e:
            logger.error("Error calculating top items summary", exc_info=True)
            return {
                'top_artist': {'name': None, 'play_count': 0},
                'top_album': {'name': None, 'artist_name': None, 'play_count': 0},
                'top_track': {'name': None, 'artist_name': None, 'album_name': None, 'play_count': 0}
            }

    def get_recent_activity_stats(self):
        """
        Get recent activity statistics (last 7 days, 30 days).
        """
        cache_key = 'dashboard_recent_activity'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data

        try:
            now = timezone.now()
            last_7_days = now - timedelta(days=7)
            last_30_days = now - timedelta(days=30)

            # Recent scrobble counts
            recent_7_days = Scrobble.objects.filter(timestamp__gte=last_7_days).count()
            recent_30_days = Scrobble.objects.filter(timestamp__gte=last_30_days).count()

            # Calculate daily average
            daily_avg_7_days = recent_7_days / 7
            daily_avg_30_days = recent_30_days / 30

            result = {
                'scrobbles_7_days': recent_7_days,
                'scrobbles_30_days': recent_30_days,
                'daily_average_7_days': daily_avg_7_days,
                'daily_average_30_days': daily_avg_30_days,
            }

            # Cache for 30 minutes
            cache.set(cache_key, result, 1800)
            logger.debug("Recent activity stats calculated", extra=result)
            return result

        except Exception as e:
            logger.error("Error calculating recent activity stats", exc_info=True)
            return {
                'scrobbles_7_days': 0,
                'scrobbles_30_days': 0,
                'daily_average_7_days': 0,
                'daily_average_30_days': 0,
            }

    def get_sync_status(self):
        """
        Get the current sync status from the database.
        """
        try:
            sync_status = SyncStatus.objects.first()
            if not sync_status:
                return {
                    'status': 'idle',
                    'last_sync': None,
                    'error_message': None,
                    'sync_count': 0
                }

            return {
                'status': sync_status.status,
                'last_sync': sync_status.last_sync_timestamp,
                'error_message': sync_status.error_message,
                'sync_count': sync_status.sync_count
            }

        except Exception as e:
            logger.error("Error getting sync status", exc_info=True)
            return {
                'status': 'error',
                'last_sync': None,
                'error_message': str(e),
                'sync_count': 0
            }

    def get_comprehensive_dashboard_data(self):
        """
        Get all dashboard data in a single call for efficiency.
        """
        logger.info("Generating comprehensive dashboard data")

        return {
            'basic_counts': self.get_basic_counts(),
            'listening_streak': self.get_listening_streak(),
            'listening_time': self.get_listening_time_estimates(),
            'top_items': self.get_top_items_summary(),
            'recent_activity': self.get_recent_activity_stats(),
            'sync_status': self.get_sync_status(),
        }


def clear_dashboard_cache():
    """
    Clear all dashboard-related cache entries.
    Useful after data imports or updates.
    """
    cache_keys = [
        'dashboard_basic_counts',
        'dashboard_listening_streak',
        'dashboard_listening_time',
        'dashboard_top_items',
        'dashboard_recent_activity'
    ]

    for key in cache_keys:
        cache.delete(key)

    logger.info("Dashboard cache cleared")