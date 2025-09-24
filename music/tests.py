from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Artist, Album, Track, Scrobble, SyncStatus


class ArtistModelTest(TestCase):
    def test_artist_creation(self):
        """Test basic artist creation."""
        artist = Artist.objects.create(
            name="The Beatles",
            mbid="b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d",
            url="https://musicbrainz.org/artist/b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        )
        self.assertEqual(str(artist), "The Beatles")
        self.assertEqual(artist.name, "The Beatles")

    def test_artist_without_mbid(self):
        """Test artist creation without MBID."""
        artist = Artist.objects.create(name="Unknown Artist")
        self.assertEqual(str(artist), "Unknown Artist")
        self.assertIsNone(artist.mbid)

    def test_invalid_mbid_format(self):
        """Test that invalid MBID format raises validation error."""
        artist = Artist(name="Test Artist", mbid="invalid-mbid")
        with self.assertRaises(ValidationError):
            artist.full_clean()

    def test_duplicate_mbid_constraint(self):
        """Test that duplicate MBIDs are not allowed."""
        mbid = "b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        Artist.objects.create(name="Artist 1", mbid=mbid)
        with self.assertRaises(IntegrityError):
            Artist.objects.create(name="Artist 2", mbid=mbid)

    def test_artist_count_methods(self):
        """Test artist count methods."""
        artist = Artist.objects.create(name="Test Artist")
        album = Album.objects.create(name="Test Album", artist=artist)
        track = Track.objects.create(name="Test Track", artist=artist, album=album)
        Scrobble.objects.create(track=track, timestamp=timezone.now())

        self.assertEqual(artist.get_album_count(), 1)
        self.assertEqual(artist.get_track_count(), 1)
        self.assertEqual(artist.get_scrobble_count(), 1)


class AlbumModelTest(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="Test Artist")

    def test_album_creation(self):
        """Test basic album creation."""
        album = Album.objects.create(
            name="Test Album",
            artist=self.artist,
            mbid="b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        )
        self.assertEqual(str(album), "Test Album by Test Artist")

    def test_unique_album_per_artist_constraint(self):
        """Test that same album name by same artist is not allowed."""
        Album.objects.create(name="Duplicate Album", artist=self.artist)
        with self.assertRaises(IntegrityError):
            Album.objects.create(name="Duplicate Album", artist=self.artist)

    def test_album_count_methods(self):
        """Test album count methods."""
        album = Album.objects.create(name="Test Album", artist=self.artist)
        track = Track.objects.create(name="Test Track", artist=self.artist, album=album)
        Scrobble.objects.create(track=track, timestamp=timezone.now())

        self.assertEqual(album.get_track_count(), 1)
        self.assertEqual(album.get_scrobble_count(), 1)


class TrackModelTest(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="Test Artist")
        self.album = Album.objects.create(name="Test Album", artist=self.artist)

    def test_track_creation_with_album(self):
        """Test track creation with album."""
        track = Track.objects.create(
            name="Test Track",
            artist=self.artist,
            album=self.album,
            duration=240
        )
        self.assertEqual(str(track), "Test Track by Test Artist (from Test Album)")

    def test_track_creation_without_album(self):
        """Test track creation without album."""
        track = Track.objects.create(
            name="Test Track",
            artist=self.artist
        )
        self.assertEqual(str(track), "Test Track by Test Artist")

    def test_duration_formatted_method(self):
        """Test duration formatting."""
        track = Track.objects.create(
            name="Test Track",
            artist=self.artist,
            duration=185  # 3:05
        )
        self.assertEqual(track.get_duration_formatted(), "3:05")

        # Test track without duration
        track_no_duration = Track.objects.create(
            name="Track No Duration",
            artist=self.artist
        )
        self.assertIsNone(track_no_duration.get_duration_formatted())

    def test_track_scrobble_count(self):
        """Test track scrobble counting."""
        track = Track.objects.create(name="Test Track", artist=self.artist)

        # Add multiple scrobbles
        for i in range(3):
            Scrobble.objects.create(
                track=track,
                timestamp=timezone.now() - timedelta(hours=i)
            )

        self.assertEqual(track.get_scrobble_count(), 3)


class ScrobbleModelTest(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="Test Artist")
        self.album = Album.objects.create(name="Test Album", artist=self.artist)
        self.track = Track.objects.create(
            name="Test Track",
            artist=self.artist,
            album=self.album
        )

    def test_scrobble_creation(self):
        """Test basic scrobble creation."""
        now = timezone.now()
        scrobble = Scrobble.objects.create(
            track=self.track,
            timestamp=now,
            lastfm_reference_id="12345"
        )
        self.assertEqual(scrobble.track, self.track)
        self.assertEqual(scrobble.timestamp, now)

    def test_scrobble_unique_constraint(self):
        """Test that duplicate scrobbles (same track + timestamp) are not allowed."""
        now = timezone.now()
        Scrobble.objects.create(track=self.track, timestamp=now)
        with self.assertRaises(IntegrityError):
            Scrobble.objects.create(track=self.track, timestamp=now)

    def test_scrobble_convenience_properties(self):
        """Test scrobble convenience properties."""
        scrobble = Scrobble.objects.create(
            track=self.track,
            timestamp=timezone.now()
        )
        self.assertEqual(scrobble.artist, self.artist)
        self.assertEqual(scrobble.album, self.album)


class SyncStatusModelTest(TestCase):
    def test_sync_status_creation(self):
        """Test basic sync status creation."""
        sync_status = SyncStatus.objects.create()
        self.assertEqual(sync_status.status, 'idle')
        self.assertEqual(sync_status.sync_count, 0)

    def test_sync_status_methods(self):
        """Test sync status management methods."""
        sync_status = SyncStatus.objects.create()

        # Test mark_sync_started
        sync_status.mark_sync_started()
        sync_status.refresh_from_db()
        self.assertEqual(sync_status.status, 'syncing')
        self.assertIsNone(sync_status.error_message)

        # Test mark_sync_success
        sync_status.mark_sync_success()
        sync_status.refresh_from_db()
        self.assertEqual(sync_status.status, 'success')
        self.assertEqual(sync_status.sync_count, 1)
        self.assertIsNotNone(sync_status.last_sync_timestamp)

        # Test mark_sync_error
        error_msg = "Test error message"
        sync_status.mark_sync_error(error_msg)
        sync_status.refresh_from_db()
        self.assertEqual(sync_status.status, 'error')
        self.assertEqual(sync_status.error_message, error_msg)

    def test_sync_status_string_representation(self):
        """Test string representation with and without last sync."""
        sync_status = SyncStatus.objects.create()
        self.assertIn('Sync status: idle', str(sync_status))

        sync_status.mark_sync_success()
        sync_status.refresh_from_db()
        self.assertIn('Sync success', str(sync_status))
        self.assertIn('Last:', str(sync_status))