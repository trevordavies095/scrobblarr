from django.contrib import admin
from .models import Artist, Album, Track, Scrobble, SyncStatus


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ['name', 'mbid', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ['name', 'artist', 'mbid', 'created_at']
    list_filter = ['artist', 'created_at']
    search_fields = ['name', 'artist__name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ['name', 'artist', 'album', 'duration', 'created_at']
    list_filter = ['artist', 'album', 'created_at']
    search_fields = ['name', 'artist__name', 'album__name', 'mbid']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Scrobble)
class ScrobbleAdmin(admin.ModelAdmin):
    list_display = ['track', 'timestamp', 'created_at']
    list_filter = ['timestamp', 'created_at']
    search_fields = ['track__name', 'track__artist__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'timestamp'


@admin.register(SyncStatus)
class SyncStatusAdmin(admin.ModelAdmin):
    list_display = ['status', 'last_sync_timestamp', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at', 'updated_at']