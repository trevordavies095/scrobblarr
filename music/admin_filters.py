"""
Custom admin filters for enhanced data browsing and filtering capabilities.
"""
from datetime import datetime, timedelta
from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MissingMBIDFilter(admin.SimpleListFilter):
    """Filter for records with or without MusicBrainz IDs."""
    title = _('MBID Status')
    parameter_name = 'mbid_status'

    def lookups(self, request, model_admin):
        return (
            ('missing', _('Missing MBID')),
            ('present', _('Has MBID')),
            ('invalid', _('Invalid MBID format')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'missing':
            return queryset.filter(Q(mbid__isnull=True) | Q(mbid=''))
        elif self.value() == 'present':
            return queryset.exclude(Q(mbid__isnull=True) | Q(mbid=''))
        elif self.value() == 'invalid':
            # Find MBIDs that don't match UUID format
            return queryset.exclude(Q(mbid__isnull=True) | Q(mbid='')).exclude(
                mbid__regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            )
        return queryset


class PlayCountFilter(admin.SimpleListFilter):
    """Filter for records by play count ranges."""
    title = _('Play Count')
    parameter_name = 'play_count'

    def lookups(self, request, model_admin):
        return (
            ('unplayed', _('No plays (0)')),
            ('low', _('Low plays (1-9)')),
            ('medium', _('Medium plays (10-49)')),
            ('high', _('High plays (50-99)')),
            ('very_high', _('Very high plays (100+)')),
        )

    def queryset(self, request, queryset):
        # This will be used differently depending on the model
        # The implementing admin will need to override this or use annotations
        return queryset


class ArtistPlayCountFilter(PlayCountFilter):
    """Play count filter specifically for artists."""

    def queryset(self, request, queryset):
        # Annotate queryset with scrobble count if not already done
        if not hasattr(queryset.model, '_annotated_scrobble_count'):
            queryset = queryset.annotate(
                total_scrobbles=Count('tracks__scrobbles')
            )

        if self.value() == 'unplayed':
            return queryset.filter(total_scrobbles=0)
        elif self.value() == 'low':
            return queryset.filter(total_scrobbles__range=(1, 9))
        elif self.value() == 'medium':
            return queryset.filter(total_scrobbles__range=(10, 49))
        elif self.value() == 'high':
            return queryset.filter(total_scrobbles__range=(50, 99))
        elif self.value() == 'very_high':
            return queryset.filter(total_scrobbles__gte=100)
        return queryset


class AlbumPlayCountFilter(PlayCountFilter):
    """Play count filter specifically for albums."""

    def queryset(self, request, queryset):
        if not hasattr(queryset.model, '_annotated_scrobble_count'):
            queryset = queryset.annotate(
                total_scrobbles=Count('tracks__scrobbles')
            )

        if self.value() == 'unplayed':
            return queryset.filter(total_scrobbles=0)
        elif self.value() == 'low':
            return queryset.filter(total_scrobbles__range=(1, 9))
        elif self.value() == 'medium':
            return queryset.filter(total_scrobbles__range=(10, 49))
        elif self.value() == 'high':
            return queryset.filter(total_scrobbles__range=(50, 99))
        elif self.value() == 'very_high':
            return queryset.filter(total_scrobbles__gte=100)
        return queryset


class TrackPlayCountFilter(PlayCountFilter):
    """Play count filter specifically for tracks."""

    def queryset(self, request, queryset):
        if not hasattr(queryset.model, '_annotated_scrobble_count'):
            queryset = queryset.annotate(
                total_scrobbles=Count('scrobbles')
            )

        if self.value() == 'unplayed':
            return queryset.filter(total_scrobbles=0)
        elif self.value() == 'low':
            return queryset.filter(total_scrobbles__range=(1, 9))
        elif self.value() == 'medium':
            return queryset.filter(total_scrobbles__range=(10, 49))
        elif self.value() == 'high':
            return queryset.filter(total_scrobbles__range=(50, 99))
        elif self.value() == 'very_high':
            return queryset.filter(total_scrobbles__gte=100)
        return queryset


class CreatedDateFilter(admin.SimpleListFilter):
    """Filter for records by creation date ranges."""
    title = _('Import Date')
    parameter_name = 'import_date'

    def lookups(self, request, model_admin):
        return (
            ('today', _('Today')),
            ('yesterday', _('Yesterday')),
            ('week', _('Past week')),
            ('month', _('Past month')),
            ('quarter', _('Past 3 months')),
            ('year', _('Past year')),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if self.value() == 'today':
            return queryset.filter(created_at__gte=today_start)
        elif self.value() == 'yesterday':
            yesterday_start = today_start - timedelta(days=1)
            return queryset.filter(
                created_at__gte=yesterday_start,
                created_at__lt=today_start
            )
        elif self.value() == 'week':
            week_start = today_start - timedelta(days=7)
            return queryset.filter(created_at__gte=week_start)
        elif self.value() == 'month':
            month_start = today_start - timedelta(days=30)
            return queryset.filter(created_at__gte=month_start)
        elif self.value() == 'quarter':
            quarter_start = today_start - timedelta(days=90)
            return queryset.filter(created_at__gte=quarter_start)
        elif self.value() == 'year':
            year_start = today_start - timedelta(days=365)
            return queryset.filter(created_at__gte=year_start)
        return queryset


class RecentActivityFilter(admin.SimpleListFilter):
    """Filter artists by their recent scrobbling activity."""
    title = _('Recent Activity')
    parameter_name = 'recent_activity'

    def lookups(self, request, model_admin):
        return (
            ('today', _('Played today')),
            ('week', _('Played this week')),
            ('month', _('Played this month')),
            ('quarter', _('Played in past 3 months')),
            ('inactive_month', _('Not played in 1 month+')),
            ('inactive_year', _('Not played in 1 year+')),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if self.value() == 'today':
            return queryset.filter(
                tracks__scrobbles__timestamp__gte=today_start
            ).distinct()
        elif self.value() == 'week':
            week_start = today_start - timedelta(days=7)
            return queryset.filter(
                tracks__scrobbles__timestamp__gte=week_start
            ).distinct()
        elif self.value() == 'month':
            month_start = today_start - timedelta(days=30)
            return queryset.filter(
                tracks__scrobbles__timestamp__gte=month_start
            ).distinct()
        elif self.value() == 'quarter':
            quarter_start = today_start - timedelta(days=90)
            return queryset.filter(
                tracks__scrobbles__timestamp__gte=quarter_start
            ).distinct()
        elif self.value() == 'inactive_month':
            month_ago = today_start - timedelta(days=30)
            return queryset.exclude(
                tracks__scrobbles__timestamp__gte=month_ago
            ).distinct()
        elif self.value() == 'inactive_year':
            year_ago = today_start - timedelta(days=365)
            return queryset.exclude(
                tracks__scrobbles__timestamp__gte=year_ago
            ).distinct()
        return queryset


class DurationRangeFilter(admin.SimpleListFilter):
    """Filter tracks by duration ranges."""
    title = _('Track Duration')
    parameter_name = 'duration'

    def lookups(self, request, model_admin):
        return (
            ('no_duration', _('Unknown duration')),
            ('very_short', _('Very short (< 1 min)')),
            ('short', _('Short (1-3 mins)')),
            ('normal', _('Normal (3-6 mins)')),
            ('long', _('Long (6-10 mins)')),
            ('very_long', _('Very long (10+ mins)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'no_duration':
            return queryset.filter(Q(duration__isnull=True) | Q(duration=0))
        elif self.value() == 'very_short':
            return queryset.filter(duration__gt=0, duration__lt=60)
        elif self.value() == 'short':
            return queryset.filter(duration__range=(60, 180))
        elif self.value() == 'normal':
            return queryset.filter(duration__range=(180, 360))
        elif self.value() == 'long':
            return queryset.filter(duration__range=(360, 600))
        elif self.value() == 'very_long':
            return queryset.filter(duration__gte=600)
        return queryset


class AlbumStatusFilter(admin.SimpleListFilter):
    """Filter tracks by whether they have an album association."""
    title = _('Album Status')
    parameter_name = 'album_status'

    def lookups(self, request, model_admin):
        return (
            ('with_album', _('Has Album')),
            ('without_album', _('No Album (Singles)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'with_album':
            return queryset.filter(album__isnull=False)
        elif self.value() == 'without_album':
            return queryset.filter(album__isnull=True)
        return queryset


class ScrobbleAgeFilter(admin.SimpleListFilter):
    """Filter scrobbles by how old they are."""
    title = _('Scrobble Age')
    parameter_name = 'scrobble_age'

    def lookups(self, request, model_admin):
        return (
            ('today', _('Today')),
            ('week', _('This week')),
            ('month', _('This month')),
            ('year', _('This year')),
            ('old', _('Older than 1 year')),
            ('very_old', _('Before 2010')),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if self.value() == 'today':
            return queryset.filter(timestamp__gte=today_start)
        elif self.value() == 'week':
            week_start = today_start - timedelta(days=7)
            return queryset.filter(timestamp__gte=week_start)
        elif self.value() == 'month':
            month_start = today_start - timedelta(days=30)
            return queryset.filter(timestamp__gte=month_start)
        elif self.value() == 'year':
            year_start = datetime(now.year, 1, 1, tzinfo=now.tzinfo)
            return queryset.filter(timestamp__gte=year_start)
        elif self.value() == 'old':
            year_ago = today_start - timedelta(days=365)
            return queryset.filter(timestamp__lt=year_ago)
        elif self.value() == 'very_old':
            cutoff_2010 = datetime(2010, 1, 1, tzinfo=now.tzinfo)
            return queryset.filter(timestamp__lt=cutoff_2010)
        return queryset


class DataQualityFilter(admin.SimpleListFilter):
    """Filter records by data quality indicators."""
    title = _('Data Quality')
    parameter_name = 'data_quality'

    def lookups(self, request, model_admin):
        return (
            ('complete', _('Complete (has all data)')),
            ('missing_mbid', _('Missing MBID')),
            ('missing_url', _('Missing URL')),
            ('needs_review', _('Needs review')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'complete':
            return queryset.exclude(
                Q(mbid__isnull=True) | Q(mbid='') |
                Q(url__isnull=True) | Q(url='')
            )
        elif self.value() == 'missing_mbid':
            return queryset.filter(Q(mbid__isnull=True) | Q(mbid=''))
        elif self.value() == 'missing_url':
            return queryset.filter(Q(url__isnull=True) | Q(url=''))
        elif self.value() == 'needs_review':
            # Records with potential data quality issues
            return queryset.filter(
                Q(mbid__isnull=True) | Q(mbid='') |
                Q(url__isnull=True) | Q(url='') |
                Q(name__icontains='unknown') |
                Q(name__icontains='untitled')
            )
        return queryset