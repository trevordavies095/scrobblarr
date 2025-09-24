from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Max, Q
from django.utils import timezone

from .models import Artist, Album, Track, Scrobble, SyncStatus
from .admin_filters import (
    MissingMBIDFilter, ArtistPlayCountFilter, AlbumPlayCountFilter, TrackPlayCountFilter,
    CreatedDateFilter, RecentActivityFilter, DurationRangeFilter, AlbumStatusFilter,
    ScrobbleAgeFilter, DataQualityFilter
)
from .admin_actions import (
    export_to_csv, validate_selected_records, remove_duplicates, clear_invalid_mbids,
    bulk_update_urls, generate_data_quality_report, merge_duplicate_artists,
    update_track_durations
)
from .admin_mixins import (
    EnhancedAdminMixin, CountDisplayMixin, BulkActionMixin, MBIDStatusMixin,
    RecentActivityMixin, PerformanceOptimizedMixin, FilterMixin, DataQualityMixin,
    LinkableMixin, TimestampMixin
)


@admin.register(Artist)
class ArtistAdmin(
    EnhancedAdminMixin,
    CountDisplayMixin,
    BulkActionMixin,
    MBIDStatusMixin,
    RecentActivityMixin,
    PerformanceOptimizedMixin,
    FilterMixin,
    DataQualityMixin,
    LinkableMixin,
    TimestampMixin,
    admin.ModelAdmin
):
    list_display = [
        'name',
        'mbid_status_display',
        'track_count_display',
        'album_count_display',
        'scrobble_count_display',
        'recent_activity_display',
        'data_quality_score',
        'created_at'
    ]
    list_filter = [
        MissingMBIDFilter,
        ArtistPlayCountFilter,
        RecentActivityFilter,
        CreatedDateFilter,
        DataQualityFilter,
    ]
    search_fields = ['=name', 'mbid', '^name']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = []
    ordering = ['-created_at']
    list_editable = ['url']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            track_count=Count('tracks', distinct=True),
            album_count=Count('albums', distinct=True),
            scrobble_count=Count('tracks__scrobbles', distinct=True),
            last_scrobble_date=Max('tracks__scrobbles__timestamp')
        )

    def track_count_display(self, obj):
        count = getattr(obj, 'track_count', 0)
        return self.create_changelist_link(
            'track', 'artist__id__exact', obj.id, count, f'{count:,} tracks'
        )
    track_count_display.short_description = 'Tracks'
    track_count_display.admin_order_field = 'track_count'

    def album_count_display(self, obj):
        count = getattr(obj, 'album_count', 0)
        return self.create_changelist_link(
            'album', 'artist__id__exact', obj.id, count, f'{count:,} albums'
        )
    album_count_display.short_description = 'Albums'
    album_count_display.admin_order_field = 'album_count'

    def scrobble_count_display(self, obj):
        count = getattr(obj, 'scrobble_count', 0)
        display = self.create_changelist_link(
            'scrobble', 'track__artist__id__exact', obj.id, count, f'{count:,}'
        )
        return self.get_play_count_display(obj, count) if count > 0 else display
    scrobble_count_display.short_description = 'Total Plays'
    scrobble_count_display.admin_order_field = 'scrobble_count'

    def recent_activity_display(self, obj):
        last_scrobble = getattr(obj, 'last_scrobble_date', None)
        if last_scrobble:
            time_ago = self.get_time_ago(last_scrobble)
            return format_html(
                '<span title="{}">{}</span>',
                self.format_timestamp(last_scrobble),
                time_ago
            )
        return format_html('<span style="color: #6c757d;">Never</span>')
    recent_activity_display.short_description = 'Last Played'
    recent_activity_display.admin_order_field = 'last_scrobble_date'

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions['merge_duplicate_artists'] = (
            merge_duplicate_artists,
            'merge_duplicate_artists',
            merge_duplicate_artists.short_description
        )
        return actions




@admin.register(Album)
class AlbumAdmin(
    EnhancedAdminMixin,
    CountDisplayMixin,
    BulkActionMixin,
    MBIDStatusMixin,
    PerformanceOptimizedMixin,
    FilterMixin,
    DataQualityMixin,
    LinkableMixin,
    TimestampMixin,
    admin.ModelAdmin
):
    list_display = [
        'name',
        'artist_link_display',
        'mbid_status_display',
        'track_count_display',
        'scrobble_count_display',
        'data_quality_score',
        'created_at'
    ]
    list_filter = [
        'artist',
        MissingMBIDFilter,
        AlbumPlayCountFilter,
        CreatedDateFilter,
        DataQualityFilter,
    ]
    search_fields = ['=name', 'artist__name', '^name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['artist']
    ordering = ['-created_at']
    autocomplete_fields = ['artist']
    list_editable = ['url']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('artist').annotate(
            track_count=Count('tracks', distinct=True),
            scrobble_count=Count('tracks__scrobbles', distinct=True)
        )

    def artist_link_display(self, obj):
        return self.create_admin_link(obj.artist)
    artist_link_display.short_description = 'Artist'
    artist_link_display.admin_order_field = 'artist__name'

    def track_count_display(self, obj):
        count = getattr(obj, 'track_count', 0)
        return self.create_changelist_link(
            'track', 'album__id__exact', obj.id, count, f'{count:,} tracks'
        )
    track_count_display.short_description = 'Tracks'
    track_count_display.admin_order_field = 'track_count'

    def scrobble_count_display(self, obj):
        count = getattr(obj, 'scrobble_count', 0)
        display = self.create_changelist_link(
            'scrobble', 'track__album__id__exact', obj.id, count, f'{count:,}'
        )
        return self.get_play_count_display(obj, count) if count > 0 else display
    scrobble_count_display.short_description = 'Total Plays'
    scrobble_count_display.admin_order_field = 'scrobble_count'




@admin.register(Track)
class TrackAdmin(
    EnhancedAdminMixin,
    CountDisplayMixin,
    BulkActionMixin,
    MBIDStatusMixin,
    PerformanceOptimizedMixin,
    FilterMixin,
    DataQualityMixin,
    LinkableMixin,
    TimestampMixin,
    admin.ModelAdmin
):
    list_display = [
        'name',
        'artist_link_display',
        'album_link_display',
        'duration_formatted',
        'mbid_status_display',
        'scrobble_count_display',
        'data_quality_score',
        'created_at'
    ]
    list_filter = [
        'artist',
        'album',
        MissingMBIDFilter,
        TrackPlayCountFilter,
        DurationRangeFilter,
        AlbumStatusFilter,
        CreatedDateFilter,
        DataQualityFilter,
    ]
    search_fields = ['=name', 'artist__name', 'album__name', '^name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['artist', 'album']
    ordering = ['-created_at']
    autocomplete_fields = ['artist', 'album']
    list_editable = ['duration', 'url']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('artist', 'album').annotate(
            scrobble_count=Count('scrobbles', distinct=True)
        )

    def artist_link_display(self, obj):
        return self.create_admin_link(obj.artist)
    artist_link_display.short_description = 'Artist'
    artist_link_display.admin_order_field = 'artist__name'

    def album_link_display(self, obj):
        return self.create_admin_link(obj.album) if obj.album else '-'
    album_link_display.short_description = 'Album'
    album_link_display.admin_order_field = 'album__name'

    def duration_formatted(self, obj):
        if obj.duration:
            minutes, seconds = divmod(obj.duration, 60)
            if obj.duration > 600:  # 10+ minutes
                return format_html('<span style="color: #dc3545; font-weight: bold;">{}:{:02d}</span>', minutes, seconds)
            elif obj.duration < 60:  # < 1 minute
                return format_html('<span style="color: #ffc107;">0:{:02d}</span>', obj.duration)
            else:
                return f"{minutes}:{seconds:02d}"
        return format_html('<span style="color: #6c757d;">Unknown</span>')
    duration_formatted.short_description = 'Duration'
    duration_formatted.admin_order_field = 'duration'

    def scrobble_count_display(self, obj):
        count = getattr(obj, 'scrobble_count', 0)
        display = self.create_changelist_link(
            'scrobble', 'track__id__exact', obj.id, count, f'{count:,}'
        )
        return self.get_play_count_display(obj, count) if count > 0 else display
    scrobble_count_display.short_description = 'Plays'
    scrobble_count_display.admin_order_field = 'scrobble_count'

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions['update_track_durations'] = (
            update_track_durations,
            'update_track_durations',
            update_track_durations.short_description
        )
        return actions




@admin.register(Scrobble)
class ScrobbleAdmin(
    EnhancedAdminMixin,
    BulkActionMixin,
    PerformanceOptimizedMixin,
    FilterMixin,
    LinkableMixin,
    TimestampMixin,
    admin.ModelAdmin
):
    list_display = [
        'track_display',
        'artist_display',
        'album_display',
        'timestamp_formatted',
        'time_ago_display',
        'import_date_display'
    ]
    list_filter = [
        'track__artist',
        'track__album',
        ScrobbleAgeFilter,
        CreatedDateFilter,
    ]
    search_fields = ['track__name', 'track__artist__name', 'track__album__name']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['track', 'track__artist', 'track__album']
    date_hierarchy = 'timestamp'
    list_per_page = 100
    ordering = ['-timestamp']

    def track_display(self, obj):
        return self.create_admin_link(obj.track)
    track_display.short_description = 'Track'
    track_display.admin_order_field = 'track__name'

    def artist_display(self, obj):
        return self.create_admin_link(obj.track.artist)
    artist_display.short_description = 'Artist'
    artist_display.admin_order_field = 'track__artist__name'

    def album_display(self, obj):
        return self.create_admin_link(obj.track.album) if obj.track.album else '-'
    album_display.short_description = 'Album'
    album_display.admin_order_field = 'track__album__name'

    def timestamp_formatted(self, obj):
        return self.format_timestamp(obj.timestamp)
    timestamp_formatted.short_description = 'Played At'
    timestamp_formatted.admin_order_field = 'timestamp'

    def time_ago_display(self, obj):
        return self.get_time_ago(obj.timestamp)
    time_ago_display.short_description = 'Time Ago'
    time_ago_display.admin_order_field = 'timestamp'

    def import_date_display(self, obj):
        return self.format_timestamp(obj.created_at, include_time=False)
    import_date_display.short_description = 'Import Date'
    import_date_display.admin_order_field = 'created_at'

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions['remove_duplicates'] = (
            remove_duplicates,
            'remove_duplicates',
            remove_duplicates.short_description
        )
        return actions




@admin.register(SyncStatus)
class SyncStatusAdmin(
    EnhancedAdminMixin,
    TimestampMixin,
    admin.ModelAdmin
):
    list_display = [
        'status_display',
        'last_sync_formatted',
        'sync_count',
        'error_preview',
        'last_updated'
    ]
    list_filter = ['status', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at', 'sync_count']
    ordering = ['-updated_at']

    def status_display(self, obj):
        colors = {
            'idle': '#6c757d',
            'syncing': '#007bff',
            'success': '#28a745',
            'error': '#dc3545',
        }
        icons = {
            'idle': '⏸',
            'syncing': '🔄',
            'success': '✅',
            'error': '❌',
        }
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '•')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'

    def last_sync_formatted(self, obj):
        if obj.last_sync_timestamp:
            return self.format_timestamp(obj.last_sync_timestamp)
        return format_html('<span style="color: #6c757d;">Never</span>')
    last_sync_formatted.short_description = 'Last Sync'
    last_sync_formatted.admin_order_field = 'last_sync_timestamp'

    def last_updated(self, obj):
        return self.get_time_ago(obj.updated_at)
    last_updated.short_description = 'Updated'
    last_updated.admin_order_field = 'updated_at'

    def error_preview(self, obj):
        if obj.error_message:
            preview = obj.error_message[:50]
            if len(obj.error_message) > 50:
                preview += '...'
            return format_html(
                '<span title="{}" style="color: #dc3545;">{}</span>',
                obj.error_message, preview
            )
        return format_html('<span style="color: #28a745;">No errors</span>')
    error_preview.short_description = 'Error Message'