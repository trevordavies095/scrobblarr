from django.db import models
from django.core.validators import RegexValidator
from core.models import TimeStampedModel
import uuid


# MBID validator for MusicBrainz IDs (UUID format)
mbid_validator = RegexValidator(
    regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    message='MBID must be a valid UUID format',
    flags=0
)


class Artist(TimeStampedModel):
    """
    Model representing a music artist.
    """
    name = models.CharField(max_length=255, db_index=True)
    mbid = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        unique=True,
        validators=[mbid_validator],
        help_text="MusicBrainz ID (UUID format)"
    )
    url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = 'artists'
        constraints = [
            models.CheckConstraint(
                check=models.Q(name__isnull=False) & ~models.Q(name=''),
                name='artist_name_not_empty'
            ),
        ]
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['mbid']),
        ]

    def __str__(self):
        return self.name

    def get_track_count(self):
        """Get total number of tracks by this artist."""
        return self.tracks.count()

    def get_scrobble_count(self):
        """Get total number of scrobbles for this artist."""
        from django.db.models import Count
        return self.tracks.aggregate(
            total_scrobbles=Count('scrobbles')
        )['total_scrobbles'] or 0

    def get_album_count(self):
        """Get total number of albums by this artist."""
        return self.albums.count()


class Album(TimeStampedModel):
    """
    Model representing a music album.
    """
    name = models.CharField(max_length=255, db_index=True)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='albums')
    mbid = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        unique=True,
        validators=[mbid_validator],
        help_text="MusicBrainz ID (UUID format)"
    )
    url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = 'albums'
        constraints = [
            models.CheckConstraint(
                check=models.Q(name__isnull=False) & ~models.Q(name=''),
                name='album_name_not_empty'
            ),
            models.UniqueConstraint(
                fields=['name', 'artist'],
                name='unique_album_per_artist'
            ),
        ]
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['artist']),
            models.Index(fields=['mbid']),
            models.Index(fields=['artist', 'name']),
        ]

    def __str__(self):
        return f"{self.name} by {self.artist.name}"

    def get_track_count(self):
        """Get total number of tracks in this album."""
        return self.tracks.count()

    def get_scrobble_count(self):
        """Get total number of scrobbles for this album."""
        from django.db.models import Count
        return self.tracks.aggregate(
            total_scrobbles=Count('scrobbles')
        )['total_scrobbles'] or 0


class Track(TimeStampedModel):
    """
    Model representing a music track.
    """
    name = models.CharField(max_length=255, db_index=True)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='tracks')
    album = models.ForeignKey(
        Album,
        on_delete=models.CASCADE,
        related_name='tracks',
        blank=True,
        null=True,
        help_text="Album (optional for standalone tracks)"
    )
    mbid = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        unique=True,
        validators=[mbid_validator],
        help_text="MusicBrainz ID (UUID format)"
    )
    url = models.URLField(blank=True, null=True)
    duration = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Track duration in seconds"
    )

    class Meta:
        db_table = 'tracks'
        constraints = [
            models.CheckConstraint(
                check=models.Q(name__isnull=False) & ~models.Q(name=''),
                name='track_name_not_empty'
            ),
            models.CheckConstraint(
                check=models.Q(duration__isnull=True) | models.Q(duration__gt=0),
                name='track_duration_positive'
            ),
        ]
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['artist']),
            models.Index(fields=['album']),
            models.Index(fields=['mbid']),
            models.Index(fields=['artist', 'name']),
            models.Index(fields=['album', 'name']),
        ]

    def __str__(self):
        if self.album:
            return f"{self.name} by {self.artist.name} (from {self.album.name})"
        return f"{self.name} by {self.artist.name}"

    def get_scrobble_count(self):
        """Get total number of scrobbles for this track."""
        return self.scrobbles.count()

    def get_duration_formatted(self):
        """Get formatted duration as MM:SS."""
        if not self.duration:
            return None
        minutes, seconds = divmod(self.duration, 60)
        return f"{minutes}:{seconds:02d}"


class Scrobble(TimeStampedModel):
    """
    Model representing a scrobble (play record).
    """
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='scrobbles')
    timestamp = models.DateTimeField(
        help_text="When the track was played",
        db_index=True
    )
    lastfm_reference_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Reference ID from Last.fm API"
    )

    class Meta:
        db_table = 'scrobbles'
        constraints = [
            models.UniqueConstraint(
                fields=['track', 'timestamp'],
                name='unique_scrobble_per_track_timestamp'
            ),
        ]
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['track']),
            models.Index(fields=['lastfm_reference_id']),
            models.Index(fields=['track', 'timestamp']),
            models.Index(fields=['-timestamp']),  # For recent queries
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.track.name} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @property
    def artist(self):
        """Convenience property to get the artist."""
        return self.track.artist

    @property
    def album(self):
        """Convenience property to get the album."""
        return self.track.album


class SyncStatus(TimeStampedModel):
    """
    Model for tracking Last.fm synchronization status.
    """
    STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]

    last_sync_timestamp = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp of last successful sync"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='idle',
        db_index=True
    )
    error_message = models.TextField(blank=True, null=True)
    sync_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of successful syncs performed"
    )

    class Meta:
        db_table = 'sync_status'
        constraints = [
            models.CheckConstraint(
                check=models.Q(sync_count__gte=0),
                name='sync_count_non_negative'
            ),
        ]

    def __str__(self):
        if self.last_sync_timestamp:
            return f"Sync {self.status} - Last: {self.last_sync_timestamp.strftime('%Y-%m-%d %H:%M')}"
        return f"Sync status: {self.status}"

    def mark_sync_started(self):
        """Mark sync as started."""
        self.status = 'syncing'
        self.error_message = None
        self.save(update_fields=['status', 'error_message', 'updated_at'])

    def mark_sync_success(self, timestamp=None):
        """Mark sync as successful."""
        from django.utils import timezone
        self.status = 'success'
        self.last_sync_timestamp = timestamp or timezone.now()
        self.sync_count += 1
        self.error_message = None
        self.save(update_fields=['status', 'last_sync_timestamp', 'sync_count', 'error_message', 'updated_at'])

    def mark_sync_error(self, error_message):
        """Mark sync as failed with error message."""
        self.status = 'error'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message', 'updated_at'])