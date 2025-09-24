from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import Artist, Album, Track, Scrobble, SyncStatus


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'mbid',
        'track_count_display',
        'album_count_display',
        'scrobble_count_display',
        'created_at'
    ]
    list_filter = ['created_at']
    search_fields = ['name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = []
    list_per_page = 50

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            track_count=Count('tracks'),
            album_count=Count('albums'),
            scrobble_count=Count('tracks__scrobbles')
        )

    def track_count_display(self, obj):
        count = getattr(obj, 'track_count', 0)
        if count > 0:
            url = reverse('admin:music_track_changelist') + f'?artist__id__exact={obj.id}'
            return format_html('<a href="{}">{} tracks</a>', url, count)
        return '0 tracks'
    track_count_display.short_description = 'Tracks'
    track_count_display.admin_order_field = 'track_count'

    def album_count_display(self, obj):
        count = getattr(obj, 'album_count', 0)
        if count > 0:
            url = reverse('admin:music_album_changelist') + f'?artist__id__exact={obj.id}'
            return format_html('<a href="{}">{} albums</a>', url, count)
        return '0 albums'
    album_count_display.short_description = 'Albums'
    album_count_display.admin_order_field = 'album_count'

    def scrobble_count_display(self, obj):
        count = getattr(obj, 'scrobble_count', 0)
        if count > 0:
            url = reverse('admin:music_scrobble_changelist') + f'?track__artist__id__exact={obj.id}'
            return format_html('<a href="{}">{} plays</a>', url, count)
        return '0 plays'
    scrobble_count_display.short_description = 'Total Plays'
    scrobble_count_display.admin_order_field = 'scrobble_count'


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'artist',
        'mbid',
        'track_count_display',
        'scrobble_count_display',
        'created_at'
    ]
    list_filter = ['artist', 'created_at']
    search_fields = ['name', 'artist__name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['artist']
    list_per_page = 50

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('artist').annotate(
            track_count=Count('tracks'),
            scrobble_count=Count('tracks__scrobbles')
        )

    def track_count_display(self, obj):
        count = getattr(obj, 'track_count', 0)
        if count > 0:
            url = reverse('admin:music_track_changelist') + f'?album__id__exact={obj.id}'
            return format_html('<a href="{}">{} tracks</a>', url, count)
        return '0 tracks'
    track_count_display.short_description = 'Tracks'
    track_count_display.admin_order_field = 'track_count'

    def scrobble_count_display(self, obj):
        count = getattr(obj, 'scrobble_count', 0)
        if count > 0:
            url = reverse('admin:music_scrobble_changelist') + f'?track__album__id__exact={obj.id}'
            return format_html('<a href="{}">{} plays</a>', url, count)
        return '0 plays'
    scrobble_count_display.short_description = 'Total Plays'
    scrobble_count_display.admin_order_field = 'scrobble_count'


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'artist',
        'album',
        'duration_formatted',
        'scrobble_count_display',
        'created_at'
    ]
    list_filter = ['artist', 'album', 'created_at']
    search_fields = ['name', 'artist__name', 'album__name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['artist', 'album']
    list_per_page = 50

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('artist', 'album').annotate(
            scrobble_count=Count('scrobbles')
        )

    def duration_formatted(self, obj):
        if obj.duration:
            minutes, seconds = divmod(obj.duration, 60)
            return f"{minutes}:{seconds:02d}"
        return '-'
    duration_formatted.short_description = 'Duration'
    duration_formatted.admin_order_field = 'duration'

    def scrobble_count_display(self, obj):
        count = getattr(obj, 'scrobble_count', 0)
        if count > 0:
            url = reverse('admin:music_scrobble_changelist') + f'?track__id__exact={obj.id}'
            return format_html('<a href="{}">{} plays</a>', url, count)
        return '0 plays'
    scrobble_count_display.short_description = 'Plays'
    scrobble_count_display.admin_order_field = 'scrobble_count'


@admin.register(Scrobble)
class ScrobbleAdmin(admin.ModelAdmin):
    list_display = [
        'track_display',
        'artist_display',
        'album_display',
        'timestamp',
        'created_at'
    ]
    list_filter = ['timestamp', 'created_at', 'track__artist', 'track__album']
    search_fields = ['track__name', 'track__artist__name', 'track__album__name']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['track', 'track__artist', 'track__album']
    date_hierarchy = 'timestamp'
    list_per_page = 100

    def track_display(self, obj):
        url = reverse('admin:music_track_change', args=[obj.track.id])
        return format_html('<a href="{}">{}</a>', url, obj.track.name)
    track_display.short_description = 'Track'
    track_display.admin_order_field = 'track__name'

    def artist_display(self, obj):
        url = reverse('admin:music_artist_change', args=[obj.track.artist.id])
        return format_html('<a href="{}">{}</a>', url, obj.track.artist.name)
    artist_display.short_description = 'Artist'
    artist_display.admin_order_field = 'track__artist__name'

    def album_display(self, obj):
        if obj.track.album:
            url = reverse('admin:music_album_change', args=[obj.track.album.id])
            return format_html('<a href="{}">{}</a>', url, obj.track.album.name)
        return '-'
    album_display.short_description = 'Album'
    album_display.admin_order_field = 'track__album__name'


@admin.register(SyncStatus)
class SyncStatusAdmin(admin.ModelAdmin):
    list_display = [
        'status_display',
        'last_sync_timestamp',
        'sync_count',
        'error_preview',
        'updated_at'
    ]
    list_filter = ['status', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25

    def status_display(self, obj):
        colors = {
            'idle': '#6c757d',
            'syncing': '#007bff',
            'success': '#28a745',
            'error': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'

    def error_preview(self, obj):
        if obj.error_message:
            preview = obj.error_message[:50]
            if len(obj.error_message) > 50:
                preview += '...'
            return format_html('<span title="{}">{}</span>', obj.error_message, preview)
        return '-'
    error_preview.short_description = 'Error Message'