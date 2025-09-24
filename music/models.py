from django.db import models
from core.models import TimeStampedModel


class Artist(TimeStampedModel):
    """
    Model representing a music artist.
    """
    name = models.CharField(max_length=255)
    mbid = models.CharField(max_length=36, blank=True, null=True, unique=True,
                           help_text="MusicBrainz ID")
    url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = 'artists'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['mbid']),
        ]

    def __str__(self):
        return self.name


class Album(TimeStampedModel):
    """
    Model representing a music album.
    """
    name = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='albums')
    mbid = models.CharField(max_length=36, blank=True, null=True, unique=True,
                           help_text="MusicBrainz ID")
    url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = 'albums'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['artist']),
            models.Index(fields=['mbid']),
        ]

    def __str__(self):
        return f"{self.name} by {self.artist.name}"


class Track(TimeStampedModel):
    """
    Model representing a music track.
    """
    name = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='tracks')
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='tracks',
                             blank=True, null=True)
    mbid = models.CharField(max_length=36, blank=True, null=True, unique=True,
                           help_text="MusicBrainz ID")
    url = models.URLField(blank=True, null=True)
    duration = models.PositiveIntegerField(blank=True, null=True,
                                         help_text="Track duration in seconds")

    class Meta:
        db_table = 'tracks'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['artist']),
            models.Index(fields=['album']),
            models.Index(fields=['mbid']),
        ]

    def __str__(self):
        return f"{self.name} by {self.artist.name}"


class Scrobble(TimeStampedModel):
    """
    Model representing a scrobble (play record).
    """
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='scrobbles')
    timestamp = models.DateTimeField(help_text="When the track was played")
    lastfm_reference_id = models.CharField(max_length=255, blank=True, null=True,
                                         help_text="Reference ID from Last.fm API")

    class Meta:
        db_table = 'scrobbles'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['track']),
            models.Index(fields=['lastfm_reference_id']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.track.name} at {self.timestamp}"


class SyncStatus(TimeStampedModel):
    """
    Model for tracking Last.fm synchronization status.
    """
    last_sync_timestamp = models.DateTimeField(blank=True, null=True,
                                             help_text="Timestamp of last successful sync")
    status = models.CharField(max_length=20, choices=[
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('success', 'Success'),
        ('error', 'Error'),
    ], default='idle')
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'sync_status'

    def __str__(self):
        return f"Sync status: {self.status}"