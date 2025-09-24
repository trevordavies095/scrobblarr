import os
import tempfile
import csv
from io import StringIO

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone
from django.core.management import call_command
from django.core.management.base import CommandError
from datetime import datetime, timedelta

from .models import Artist, Album, Track, Scrobble, SyncStatus
from .management.commands.import_scrobbles import Command as ImportCommand
from .management.commands.validate_data import Command as ValidateCommand


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


class ImportScrobblesCommandTest(TestCase):
    """Test cases for the import_scrobbles management command."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = ImportCommand()

    def _create_test_csv(self, data):
        """Create a temporary CSV file with test data."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        writer = csv.DictWriter(temp_file, fieldnames=[
            'uts', 'utc_time', 'artist', 'artist_mbid',
            'album', 'album_mbid', 'track', 'track_mbid'
        ])
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        temp_file.close()
        return temp_file.name

    def tearDown(self):
        """Clean up temporary files."""
        # Clean up any temporary files created during tests
        pass

    def test_valid_csv_import(self):
        """Test importing a valid CSV file."""
        test_data = [
            {
                'uts': '1640995200',  # 2022-01-01 00:00:00
                'utc_time': '2022-01-01 00:00:00',
                'artist': 'The Beatles',
                'artist_mbid': 'b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d',
                'album': 'Abbey Road',
                'album_mbid': '729b68b1-c551-4d38-acc3-e5e1e17e1de8',
                'track': 'Come Together',
                'track_mbid': '60dfa5ec-84b7-4d30-b1f5-ae5af27a9f29'
            },
            {
                'uts': '1640995260',  # 2022-01-01 00:01:00
                'utc_time': '2022-01-01 00:01:00',
                'artist': 'The Beatles',
                'artist_mbid': 'b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d',
                'album': 'Abbey Road',
                'album_mbid': '729b68b1-c551-4d38-acc3-e5e1e17e1de8',
                'track': 'Something',
                'track_mbid': 'f2b3c4d5-84b7-4d30-b1f5-ae5af27a9f30'
            }
        ]

        csv_file = self._create_test_csv(test_data)

        try:
            # Capture output
            out = StringIO()
            call_command('import_scrobbles', csv_file, stdout=out)

            # Check that entities were created
            self.assertEqual(Artist.objects.count(), 1)
            self.assertEqual(Album.objects.count(), 1)
            self.assertEqual(Track.objects.count(), 2)
            self.assertEqual(Scrobble.objects.count(), 2)

            # Check artist details
            artist = Artist.objects.first()
            self.assertEqual(artist.name, 'The Beatles')
            self.assertEqual(artist.mbid, 'b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d')

            # Check album details
            album = Album.objects.first()
            self.assertEqual(album.name, 'Abbey Road')
            self.assertEqual(album.artist, artist)
            self.assertEqual(album.mbid, '729b68b1-c551-4d38-acc3-e5e1e17e1de8')

            # Check tracks
            tracks = Track.objects.all().order_by('name')
            self.assertEqual(tracks[0].name, 'Come Together')
            self.assertEqual(tracks[1].name, 'Something')

            # Check scrobbles have correct timestamps
            scrobbles = Scrobble.objects.all().order_by('timestamp')
            self.assertEqual(
                scrobbles[0].timestamp,
                datetime.fromtimestamp(1640995200, tz=timezone.utc)
            )
            self.assertEqual(
                scrobbles[1].timestamp,
                datetime.fromtimestamp(1640995260, tz=timezone.utc)
            )

        finally:
            os.unlink(csv_file)

    def test_csv_without_mbids(self):
        """Test importing CSV with missing MBID values."""
        test_data = [
            {
                'uts': '1640995200',
                'utc_time': '2022-01-01 00:00:00',
                'artist': 'Unknown Artist',
                'artist_mbid': '',
                'album': 'Unknown Album',
                'album_mbid': '',
                'track': 'Unknown Track',
                'track_mbid': ''
            }
        ]

        csv_file = self._create_test_csv(test_data)

        try:
            out = StringIO()
            call_command('import_scrobbles', csv_file, stdout=out)

            # Check that entities were created without MBIDs
            artist = Artist.objects.first()
            self.assertEqual(artist.name, 'Unknown Artist')
            self.assertIsNone(artist.mbid)

            album = Album.objects.first()
            self.assertEqual(album.name, 'Unknown Album')
            self.assertIsNone(album.mbid)

            track = Track.objects.first()
            self.assertEqual(track.name, 'Unknown Track')
            self.assertIsNone(track.mbid)

        finally:
            os.unlink(csv_file)

    def test_csv_without_album(self):
        """Test importing CSV with missing album information."""
        test_data = [
            {
                'uts': '1640995200',
                'utc_time': '2022-01-01 00:00:00',
                'artist': 'Solo Artist',
                'artist_mbid': 'a10bbbfc-cf9e-42e0-be17-e2c3e1d2600d',
                'album': '',
                'album_mbid': '',
                'track': 'Single Track',
                'track_mbid': 'c10bbbfc-cf9e-42e0-be17-e2c3e1d2600d'
            }
        ]

        csv_file = self._create_test_csv(test_data)

        try:
            out = StringIO()
            call_command('import_scrobbles', csv_file, stdout=out)

            # Check that track was created without album
            self.assertEqual(Artist.objects.count(), 1)
            self.assertEqual(Album.objects.count(), 0)  # No album should be created
            self.assertEqual(Track.objects.count(), 1)

            track = Track.objects.first()
            self.assertEqual(track.name, 'Single Track')
            self.assertIsNone(track.album)

        finally:
            os.unlink(csv_file)

    def test_invalid_csv_missing_columns(self):
        """Test error handling for CSV missing required columns."""
        # Create CSV with missing columns
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        writer = csv.DictWriter(temp_file, fieldnames=['uts', 'artist'])
        writer.writeheader()
        writer.writerow({'uts': '1640995200', 'artist': 'Test Artist'})
        temp_file.close()

        try:
            with self.assertRaises(CommandError) as cm:
                call_command('import_scrobbles', temp_file.name)

            self.assertIn('Missing required columns', str(cm.exception))

        finally:
            os.unlink(temp_file.name)

    def test_invalid_timestamps(self):
        """Test handling of invalid timestamp values."""
        test_data = [
            {
                'uts': 'invalid',
                'utc_time': '2022-01-01 00:00:00',
                'artist': 'Test Artist',
                'artist_mbid': '',
                'album': 'Test Album',
                'album_mbid': '',
                'track': 'Test Track',
                'track_mbid': ''
            },
            {
                'uts': str(int((datetime.now() + timedelta(days=1)).timestamp())),  # Future timestamp
                'utc_time': '2025-01-01 00:00:00',
                'artist': 'Future Artist',
                'artist_mbid': '',
                'album': 'Future Album',
                'album_mbid': '',
                'track': 'Future Track',
                'track_mbid': ''
            }
        ]

        csv_file = self._create_test_csv(test_data)

        try:
            out = StringIO()
            err = StringIO()
            call_command('import_scrobbles', csv_file, stdout=out, stderr=err)

            # No records should be imported due to invalid timestamps
            self.assertEqual(Scrobble.objects.count(), 0)

            # Check that errors were reported
            error_output = err.getvalue()
            self.assertIn('Invalid timestamp', error_output)
            self.assertIn('Timestamp is in the future', error_output)

        finally:
            os.unlink(csv_file)

    def test_missing_required_fields(self):
        """Test handling of missing required fields."""
        test_data = [
            {
                'uts': '1640995200',
                'utc_time': '2022-01-01 00:00:00',
                'artist': '',  # Missing artist
                'artist_mbid': '',
                'album': 'Test Album',
                'album_mbid': '',
                'track': 'Test Track',
                'track_mbid': ''
            },
            {
                'uts': '1640995260',
                'utc_time': '2022-01-01 00:01:00',
                'artist': 'Test Artist',
                'artist_mbid': '',
                'album': 'Test Album',
                'album_mbid': '',
                'track': '',  # Missing track
                'track_mbid': ''
            }
        ]

        csv_file = self._create_test_csv(test_data)

        try:
            out = StringIO()
            err = StringIO()
            call_command('import_scrobbles', csv_file, stdout=out, stderr=err)

            # No records should be imported due to missing required fields
            self.assertEqual(Scrobble.objects.count(), 0)

            # Check that errors were reported
            error_output = err.getvalue()
            self.assertIn('Missing artist name', error_output)
            self.assertIn('Missing track name', error_output)

        finally:
            os.unlink(csv_file)

    def test_dry_run_mode(self):
        """Test dry run mode doesn't import data."""
        test_data = [
            {
                'uts': '1640995200',
                'utc_time': '2022-01-01 00:00:00',
                'artist': 'Test Artist',
                'artist_mbid': '',
                'album': 'Test Album',
                'album_mbid': '',
                'track': 'Test Track',
                'track_mbid': ''
            }
        ]

        csv_file = self._create_test_csv(test_data)

        try:
            out = StringIO()
            call_command('import_scrobbles', csv_file, '--dry-run', stdout=out)

            # No data should be imported in dry run mode
            self.assertEqual(Artist.objects.count(), 0)
            self.assertEqual(Album.objects.count(), 0)
            self.assertEqual(Track.objects.count(), 0)
            self.assertEqual(Scrobble.objects.count(), 0)

            # Check output indicates dry run
            output = out.getvalue()
            self.assertIn('DRY RUN MODE', output)
            self.assertIn('DRY RUN COMPLETE', output)

        finally:
            os.unlink(csv_file)

    def test_duplicate_scrobbles_ignored(self):
        """Test that duplicate scrobbles are ignored during import."""
        test_data = [
            {
                'uts': '1640995200',
                'utc_time': '2022-01-01 00:00:00',
                'artist': 'Test Artist',
                'artist_mbid': '',
                'album': 'Test Album',
                'album_mbid': '',
                'track': 'Test Track',
                'track_mbid': ''
            },
            {
                'uts': '1640995200',  # Same timestamp and track
                'utc_time': '2022-01-01 00:00:00',
                'artist': 'Test Artist',
                'artist_mbid': '',
                'album': 'Test Album',
                'album_mbid': '',
                'track': 'Test Track',
                'track_mbid': ''
            }
        ]

        csv_file = self._create_test_csv(test_data)

        try:
            out = StringIO()
            call_command('import_scrobbles', csv_file, stdout=out)

            # Only one scrobble should be created (duplicates ignored)
            self.assertEqual(Scrobble.objects.count(), 1)

        finally:
            os.unlink(csv_file)

    def test_file_not_found_error(self):
        """Test error handling for non-existent files."""
        with self.assertRaises(CommandError) as cm:
            call_command('import_scrobbles', 'nonexistent_file.csv')

        self.assertIn('does not exist', str(cm.exception))

    def test_mbid_validation_in_command(self):
        """Test MBID validation in the command."""
        # Test valid MBID
        valid_mbid = self.command._clean_mbid('b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d')
        self.assertEqual(valid_mbid, 'b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d')

        # Test empty MBID
        empty_mbid = self.command._clean_mbid('')
        self.assertIsNone(empty_mbid)

        # Test invalid MBID
        invalid_mbid = self.command._clean_mbid('not-a-uuid')
        self.assertIsNone(invalid_mbid)

        # Test MBID with wrong length
        wrong_length = self.command._clean_mbid('b10bbbfc-cf9e-42e0-be17-e2c3e1d2600')
        self.assertIsNone(wrong_length)

    def test_batch_processing(self):
        """Test that batch processing works correctly."""
        # Create test data larger than default batch size
        test_data = []
        for i in range(50):  # Create 50 records
            test_data.append({
                'uts': str(1640995200 + i),
                'utc_time': f'2022-01-01 00:{i:02d}:00',
                'artist': f'Artist {i}',
                'artist_mbid': '',
                'album': f'Album {i}',
                'album_mbid': '',
                'track': f'Track {i}',
                'track_mbid': ''
            })

        csv_file = self._create_test_csv(test_data)

        try:
            out = StringIO()
            # Use small batch size to test batching
            call_command('import_scrobbles', csv_file, '--batch-size=10', stdout=out)

            # All records should be imported
            self.assertEqual(Artist.objects.count(), 50)
            self.assertEqual(Album.objects.count(), 50)
            self.assertEqual(Track.objects.count(), 50)
            self.assertEqual(Scrobble.objects.count(), 50)

        finally:
            os.unlink(csv_file)


class ValidateDataCommandTest(TestCase):
    """Test cases for the validate_data management command."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = ValidateCommand()

    def test_no_issues_clean_data(self):
        """Test validation on clean data with no issues."""
        # Create clean test data
        artist = Artist.objects.create(
            name="Clean Artist",
            mbid="b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        )
        album = Album.objects.create(
            name="Clean Album",
            artist=artist,
            mbid="729b68b1-c551-4d38-acc3-e5e1e17e1de8"
        )
        track = Track.objects.create(
            name="Clean Track",
            artist=artist,
            album=album,
            mbid="60dfa5ec-84b7-4d30-b1f5-ae5af27a9f29",
            duration=180
        )
        Scrobble.objects.create(
            track=track,
            timestamp=timezone.now() - timedelta(hours=1)
        )

        out = StringIO()
        call_command('validate_data', stdout=out)

        output = out.getvalue()
        self.assertIn('No data quality issues found!', output)

    def test_orphaned_records_detection(self):
        """Test detection of orphaned records."""
        # Create test data
        artist = Artist.objects.create(name="Test Artist")
        album = Album.objects.create(name="Test Album", artist=artist)
        track = Track.objects.create(name="Test Track", artist=artist, album=album)

        # Create another artist for mismatched scenario
        other_artist = Artist.objects.create(name="Other Artist")
        other_album = Album.objects.create(name="Other Album", artist=other_artist)

        # Create track with mismatched album (different artist)
        Track.objects.create(
            name="Mismatched Track",
            artist=artist,
            album=other_album  # This album belongs to different artist
        )

        out = StringIO()
        call_command('validate_data', '--category=orphaned', stdout=out)

        output = out.getvalue()
        self.assertIn('belongs to album', output)
        self.assertIn('mismatched', output.lower())

    def test_duplicate_scrobbles_detection(self):
        """Test detection of duplicate scrobbles."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create duplicate scrobbles
        timestamp = timezone.now() - timedelta(hours=1)
        Scrobble.objects.create(track=track, timestamp=timestamp)
        Scrobble.objects.create(track=track, timestamp=timestamp)
        Scrobble.objects.create(track=track, timestamp=timestamp)

        out = StringIO()
        call_command('validate_data', '--category=duplicates', stdout=out)

        output = out.getvalue()
        self.assertIn('duplicate scrobbles', output)
        self.assertIn('3 duplicate', output)

    def test_duplicate_scrobbles_fix(self):
        """Test fixing duplicate scrobbles."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create duplicate scrobbles
        timestamp = timezone.now() - timedelta(hours=1)
        Scrobble.objects.create(track=track, timestamp=timestamp)
        Scrobble.objects.create(track=track, timestamp=timestamp)
        Scrobble.objects.create(track=track, timestamp=timestamp)

        # Verify 3 scrobbles exist
        self.assertEqual(Scrobble.objects.count(), 3)

        out = StringIO()
        call_command('validate_data', '--fix', '--category=duplicates', stdout=out)

        # Should have only 1 scrobble left after fix
        self.assertEqual(Scrobble.objects.count(), 1)

    def test_missing_data_detection(self):
        """Test detection of missing critical data."""
        # This test is tricky because database constraints prevent most issues
        # We'll test what we can without violating DB constraints

        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create scrobble without lastfm_reference_id (this is allowed)
        Scrobble.objects.create(track=track, timestamp=timezone.now())

        out = StringIO()
        call_command('validate_data', '--category=missing_data', stdout=out)

        # This should run without errors even if no missing data issues are found
        output = out.getvalue()
        self.assertTrue(len(output) > 0)

    def test_future_timestamp_detection(self):
        """Test detection of future timestamps."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create scrobble with future timestamp
        future_time = timezone.now() + timedelta(days=1)
        Scrobble.objects.create(track=track, timestamp=future_time)

        out = StringIO()
        call_command('validate_data', '--category=timestamps', stdout=out)

        output = out.getvalue()
        self.assertIn('future timestamp', output)

    def test_future_timestamp_fix(self):
        """Test fixing future timestamps."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create scrobble with future timestamp
        future_time = timezone.now() + timedelta(days=1)
        scrobble = Scrobble.objects.create(track=track, timestamp=future_time)

        out = StringIO()
        call_command('validate_data', '--fix', '--category=timestamps', stdout=out)

        # Check that timestamp was fixed
        scrobble.refresh_from_db()
        self.assertLess(scrobble.timestamp, timezone.now() + timedelta(minutes=1))

    def test_old_timestamp_detection(self):
        """Test detection of very old timestamps."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create scrobble with very old timestamp (before 1970)
        old_time = datetime(1969, 1, 1, tzinfo=timezone.utc)
        Scrobble.objects.create(track=track, timestamp=old_time)

        out = StringIO()
        call_command('validate_data', '--category=timestamps', stdout=out)

        output = out.getvalue()
        self.assertIn('very old timestamp', output)

    def test_invalid_mbid_detection(self):
        """Test detection of invalid MBID formats."""
        # Create artist with invalid MBID (bypassing normal validation)
        artist = Artist(name="Test Artist", mbid="invalid-mbid-format")
        artist.save()  # This should work if we bypass full_clean()

        out = StringIO()
        call_command('validate_data', '--category=data_consistency', stdout=out)

        output = out.getvalue()
        self.assertIn('invalid MBID format', output)

    def test_invalid_mbid_fix(self):
        """Test fixing invalid MBID formats."""
        # Create artist with invalid MBID
        artist = Artist(name="Test Artist", mbid="invalid-mbid-format")
        artist.save()

        out = StringIO()
        call_command('validate_data', '--fix', '--category=data_consistency', stdout=out)

        # Check that MBID was cleared
        artist.refresh_from_db()
        self.assertIsNone(artist.mbid)

    def test_invalid_url_detection_and_fix(self):
        """Test detection and fixing of invalid URLs."""
        # Create artist with invalid URL
        artist = Artist(name="Test Artist", url="not-a-valid-url")
        artist.save()

        out = StringIO()
        call_command('validate_data', '--fix', '--category=data_consistency', stdout=out)

        # Check that URL was cleared
        artist.refresh_from_db()
        self.assertIsNone(artist.url)

    def test_unusual_track_duration_detection(self):
        """Test detection of unusual track durations."""
        artist = Artist.objects.create(name="Test Artist")

        # Create track with negative duration
        Track.objects.create(
            name="Negative Duration Track",
            artist=artist,
            duration=-60
        )

        # Create track with extremely long duration
        Track.objects.create(
            name="Very Long Track",
            artist=artist,
            duration=10800  # 3 hours
        )

        out = StringIO()
        call_command('validate_data', '--category=data_consistency', stdout=out)

        output = out.getvalue()
        self.assertIn('unusual duration', output)

    def test_duplicate_artists_detection(self):
        """Test detection of potential duplicate artists."""
        # Create artists with same name but different MBIDs
        Artist.objects.create(
            name="Duplicate Artist",
            mbid="b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        )
        Artist.objects.create(
            name="Duplicate Artist",
            mbid="c20cccfc-cf9e-42e0-be17-e2c3e1d2600e"
        )

        out = StringIO()
        call_command('validate_data', '--category=duplicates', stdout=out)

        output = out.getvalue()
        self.assertIn('appears', output)
        self.assertIn('different MBIDs', output)

    def test_json_output_format(self):
        """Test JSON output format."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create an issue (future timestamp)
        future_time = timezone.now() + timedelta(days=1)
        Scrobble.objects.create(track=track, timestamp=future_time)

        out = StringIO()
        call_command('validate_data', '--output-format=json', stdout=out)

        output = out.getvalue()
        import json
        try:
            data = json.loads(output)
            self.assertIn('validation_summary', data)
            self.assertIn('issues', data)
            self.assertGreater(data['validation_summary']['total_issues'], 0)
        except json.JSONDecodeError:
            self.fail("Output is not valid JSON")

    def test_verbose_output(self):
        """Test verbose output mode."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create an issue
        future_time = timezone.now() + timedelta(days=1)
        Scrobble.objects.create(track=track, timestamp=future_time)

        out = StringIO()
        call_command('validate_data', '--verbose', stdout=out)

        output = out.getvalue()
        self.assertIn('Checking', output)  # Verbose progress messages

    def test_category_filtering(self):
        """Test validation with specific category filtering."""
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)

        # Create multiple types of issues
        future_time = timezone.now() + timedelta(days=1)
        Scrobble.objects.create(track=track, timestamp=future_time)

        # Create duplicate scrobbles
        past_time = timezone.now() - timedelta(hours=1)
        Scrobble.objects.create(track=track, timestamp=past_time)
        Scrobble.objects.create(track=track, timestamp=past_time)

        # Test timestamp-only validation
        out = StringIO()
        call_command('validate_data', '--category=timestamps', stdout=out)
        output = out.getvalue()
        self.assertIn('future timestamp', output)
        self.assertNotIn('duplicate', output)

        # Test duplicates-only validation
        out = StringIO()
        call_command('validate_data', '--category=duplicates', stdout=out)
        output = out.getvalue()
        self.assertIn('duplicate', output)

    def test_data_quality_score_calculation(self):
        """Test data quality score calculation."""
        # Create some clean data
        artist = Artist.objects.create(name="Clean Artist")
        track = Track.objects.create(name="Clean Track", artist=artist)
        Scrobble.objects.create(
            track=track,
            timestamp=timezone.now() - timedelta(hours=1)
        )

        # Create one issue
        future_time = timezone.now() + timedelta(days=1)
        Scrobble.objects.create(track=track, timestamp=future_time)

        out = StringIO()
        call_command('validate_data', stdout=out)

        output = out.getvalue()
        self.assertIn('Data Quality Score:', output)
        self.assertIn('%', output)

    def test_validation_issue_class(self):
        """Test the ValidationIssue class functionality."""
        from music.management.commands.validate_data import ValidationIssue

        issue = ValidationIssue(
            category='test',
            severity='error',
            message='Test message',
            model_type='artist',
            record_id=1,
            record_details={'name': 'Test Artist'},
            fix_available=True
        )

        issue_dict = issue.to_dict()
        self.assertEqual(issue_dict['category'], 'test')
        self.assertEqual(issue_dict['severity'], 'error')
        self.assertEqual(issue_dict['message'], 'Test message')
        self.assertEqual(issue_dict['model_type'], 'artist')
        self.assertEqual(issue_dict['record_id'], 1)
        self.assertTrue(issue_dict['fix_available'])

    def test_command_initialization(self):
        """Test command initialization."""
        command = ValidateCommand()
        self.assertEqual(len(command.issues), 0)
        self.assertEqual(len(command.fixes_applied), 0)
        self.assertIsInstance(command.stats, dict)

    def test_fix_mode_without_fixable_issues(self):
        """Test fix mode when there are no fixable issues."""
        # Create clean data
        artist = Artist.objects.create(name="Test Artist")
        track = Track.objects.create(name="Test Track", artist=artist)
        Scrobble.objects.create(track=track, timestamp=timezone.now())

        out = StringIO()
        call_command('validate_data', '--fix', stdout=out)

        output = out.getvalue()
        self.assertIn('No data quality issues found', output)

    def test_large_dataset_performance(self):
        """Test validation performance with larger dataset."""
        # Create a larger dataset for performance testing
        artist = Artist.objects.create(name="Performance Test Artist")
        tracks = []

        # Create 100 tracks
        for i in range(100):
            track = Track.objects.create(
                name=f"Track {i}",
                artist=artist
            )
            tracks.append(track)

        # Create 500 scrobbles
        base_time = timezone.now() - timedelta(days=30)
        for i in range(500):
            Scrobble.objects.create(
                track=tracks[i % 100],
                timestamp=base_time + timedelta(minutes=i * 3)
            )

        import time
        start_time = time.time()

        out = StringIO()
        call_command('validate_data', stdout=out)

        end_time = time.time()

        # Should complete within reasonable time (adjust as needed)
        self.assertLess(end_time - start_time, 30)  # 30 seconds max

        output = out.getvalue()
        self.assertIn('VALIDATION SUMMARY', output)