import django_filters
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from music.models import Scrobble, Artist, Album, Track


class ScrobbleFilter(django_filters.FilterSet):
    """Advanced filtering for Scrobbles/Recent Tracks."""

    # Date range filtering
    from_date = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='gte',
        help_text="Filter scrobbles from this date/time (YYYY-MM-DD HH:MM:SS)"
    )
    to_date = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='lte',
        help_text="Filter scrobbles to this date/time (YYYY-MM-DD HH:MM:SS)"
    )

    # Date convenience filters
    date = django_filters.DateFilter(
        field_name='timestamp',
        lookup_expr='date',
        help_text="Filter scrobbles by specific date (YYYY-MM-DD)"
    )

    # Time period filters
    hours_ago = django_filters.NumberFilter(
        method='filter_hours_ago',
        help_text="Filter scrobbles from X hours ago until now"
    )
    days_ago = django_filters.NumberFilter(
        method='filter_days_ago',
        help_text="Filter scrobbles from X days ago until now"
    )

    # Artist filtering
    artist = django_filters.ModelChoiceFilter(
        field_name='track__artist',
        queryset=Artist.objects.all(),
        help_text="Filter by specific artist ID"
    )
    artist_name = django_filters.CharFilter(
        field_name='track__artist__name',
        lookup_expr='icontains',
        help_text="Filter by artist name (case-insensitive partial match)"
    )

    # Album filtering
    album = django_filters.ModelChoiceFilter(
        field_name='track__album',
        queryset=Album.objects.all(),
        help_text="Filter by specific album ID"
    )
    album_name = django_filters.CharFilter(
        field_name='track__album__name',
        lookup_expr='icontains',
        help_text="Filter by album name (case-insensitive partial match)"
    )

    # Track filtering
    track = django_filters.ModelChoiceFilter(
        field_name='track',
        queryset=Track.objects.all(),
        help_text="Filter by specific track ID"
    )
    track_name = django_filters.CharFilter(
        field_name='track__name',
        lookup_expr='icontains',
        help_text="Filter by track name (case-insensitive partial match)"
    )

    # Duration filtering
    min_duration = django_filters.NumberFilter(
        field_name='track__duration',
        lookup_expr='gte',
        help_text="Filter tracks with minimum duration in seconds"
    )
    max_duration = django_filters.NumberFilter(
        field_name='track__duration',
        lookup_expr='lte',
        help_text="Filter tracks with maximum duration in seconds"
    )

    # Search across multiple fields
    search = django_filters.CharFilter(
        method='filter_search',
        help_text="Search across track name, artist name, and album name"
    )

    # Recent activity filter
    recent_only = django_filters.BooleanFilter(
        method='filter_recent_only',
        help_text="Show only scrobbles from the last 24 hours"
    )

    class Meta:
        model = Scrobble
        fields = []

    def filter_hours_ago(self, queryset, name, value):
        """Filter scrobbles from X hours ago until now."""
        if value is not None:
            cutoff_time = timezone.now() - timedelta(hours=value)
            return queryset.filter(timestamp__gte=cutoff_time)
        return queryset

    def filter_days_ago(self, queryset, name, value):
        """Filter scrobbles from X days ago until now."""
        if value is not None:
            cutoff_time = timezone.now() - timedelta(days=value)
            return queryset.filter(timestamp__gte=cutoff_time)
        return queryset

    def filter_search(self, queryset, name, value):
        """Search across track, artist, and album names."""
        if value:
            return queryset.filter(
                models.Q(track__name__icontains=value) |
                models.Q(track__artist__name__icontains=value) |
                models.Q(track__album__name__icontains=value)
            )
        return queryset

    def filter_recent_only(self, queryset, name, value):
        """Filter to show only recent scrobbles (last 24 hours)."""
        if value:
            cutoff_time = timezone.now() - timedelta(hours=24)
            return queryset.filter(timestamp__gte=cutoff_time)
        return queryset


class DateRangeFilter(django_filters.FilterSet):
    """Simplified date range filter for statistics endpoints."""

    from_date = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='gte'
    )
    to_date = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='lte'
    )

    # Predefined periods
    period = django_filters.ChoiceFilter(
        method='filter_period',
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('7d', 'Last 7 days'),
            ('30d', 'Last 30 days'),
            ('90d', 'Last 90 days'),
            ('365d', 'Last year'),
            ('all', 'All time'),
        ]
    )

    class Meta:
        model = Scrobble
        fields = []

    def filter_period(self, queryset, name, value):
        """Filter by predefined time periods."""
        if not value:
            return queryset

        now = timezone.now()

        if value == 'today':
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(timestamp__gte=start_of_day)
        elif value == 'yesterday':
            yesterday = now - timedelta(days=1)
            start_of_yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(
                timestamp__gte=start_of_yesterday,
                timestamp__lt=start_of_today
            )
        elif value == '7d':
            cutoff = now - timedelta(days=7)
            return queryset.filter(timestamp__gte=cutoff)
        elif value == '30d':
            cutoff = now - timedelta(days=30)
            return queryset.filter(timestamp__gte=cutoff)
        elif value == '90d':
            cutoff = now - timedelta(days=90)
            return queryset.filter(timestamp__gte=cutoff)
        elif value == '365d':
            cutoff = now - timedelta(days=365)
            return queryset.filter(timestamp__gte=cutoff)
        elif value == 'all':
            return queryset

        return queryset