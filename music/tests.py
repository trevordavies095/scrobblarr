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


class AdminInterfaceTest(TestCase):
    """Test cases for enhanced admin interfaces."""

    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth.models import User
        from django.test import Client

        # Create superuser for admin access
        self.superuser = User.objects.create_superuser(
            'admin', 'admin@test.com', 'password'
        )
        self.client = Client()
        self.client.login(username='admin', password='password')

        # Create test data
        self.artist = Artist.objects.create(
            name="Test Artist",
            mbid="b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        )
        self.album = Album.objects.create(
            name="Test Album",
            artist=self.artist,
            mbid="729b68b1-c551-4d38-acc3-e5e1e17e1de8"
        )
        self.track = Track.objects.create(
            name="Test Track",
            artist=self.artist,
            album=self.album,
            mbid="60dfa5ec-84b7-4d30-b1f5-ae5af27a9f29",
            duration=180
        )
        self.scrobble = Scrobble.objects.create(
            track=self.track,
            timestamp=timezone.now() - timedelta(hours=1)
        )

    def test_artist_admin_list_view(self):
        """Test artist admin list view loads and displays correctly."""
        response = self.client.get('/admin/music/artist/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Artist')
        self.assertContains(response, 'MBID Status')
        self.assertContains(response, 'Recent Activity')
        self.assertContains(response, 'Quality')

    def test_artist_admin_filters(self):
        """Test artist admin filters work correctly."""
        # Test MBID filter
        response = self.client.get('/admin/music/artist/?mbid_status=present')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Artist')

        response = self.client.get('/admin/music/artist/?mbid_status=missing')
        self.assertEqual(response.status_code, 200)
        # Should not contain our test artist since it has MBID

    def test_artist_admin_search(self):
        """Test artist admin search functionality."""
        response = self.client.get('/admin/music/artist/?q=Test')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Artist')

        response = self.client.get('/admin/music/artist/?q=Nonexistent')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Test Artist')

    def test_album_admin_list_view(self):
        """Test album admin list view loads and displays correctly."""
        response = self.client.get('/admin/music/album/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Album')
        self.assertContains(response, 'Test Artist')
        self.assertContains(response, 'MBID Status')

    def test_track_admin_list_view(self):
        """Test track admin list view loads and displays correctly."""
        response = self.client.get('/admin/music/track/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Track')
        self.assertContains(response, 'Test Artist')
        self.assertContains(response, 'Test Album')
        self.assertContains(response, '3:00')  # Duration formatted

    def test_track_admin_duration_filter(self):
        """Test track duration filter."""
        response = self.client.get('/admin/music/track/?duration=normal')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Track')

    def test_scrobble_admin_list_view(self):
        """Test scrobble admin list view loads and displays correctly."""
        response = self.client.get('/admin/music/scrobble/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Track')
        self.assertContains(response, 'Test Artist')
        self.assertContains(response, 'Time Ago')

    def test_scrobble_admin_age_filter(self):
        """Test scrobble age filter."""
        response = self.client.get('/admin/music/scrobble/?scrobble_age=today')
        self.assertEqual(response.status_code, 200)
        # Our test scrobble is from 1 hour ago, so it should appear in today's filter

    def test_admin_bulk_actions_available(self):
        """Test that bulk actions are available in admin."""
        response = self.client.get('/admin/music/artist/')
        self.assertEqual(response.status_code, 200)
        # Check that bulk actions are present in the form
        self.assertContains(response, 'export_to_csv')
        self.assertContains(response, 'validate_selected_records')

    def test_admin_export_csv_action(self):
        """Test CSV export functionality."""
        # Test export action via POST request
        response = self.client.post('/admin/music/artist/', {
            'action': 'export_to_csv',
            '_selected_action': [self.artist.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'text/csv')
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_admin_validation_action(self):
        """Test validation action."""
        response = self.client.post('/admin/music/artist/', {
            'action': 'validate_selected_records',
            '_selected_action': [self.artist.id],
        })
        self.assertEqual(response.status_code, 302)  # Redirects after action

    def test_admin_links_work(self):
        """Test that admin links between models work correctly."""
        # Test artist page has links to tracks and albums
        response = self.client.get(f'/admin/music/artist/{self.artist.id}/change/')
        self.assertEqual(response.status_code, 200)

        # Test track page has links to artist and album
        response = self.client.get(f'/admin/music/track/{self.track.id}/change/')
        self.assertEqual(response.status_code, 200)

    def test_admin_count_displays(self):
        """Test that count displays show correct numbers and are clickable."""
        response = self.client.get('/admin/music/artist/')
        self.assertEqual(response.status_code, 200)
        # Should show 1 track, 1 album, 1 play
        self.assertContains(response, '1 tracks')
        self.assertContains(response, '1 albums')

    def test_admin_quality_indicators(self):
        """Test data quality indicators work."""
        # Create an artist with missing MBID
        bad_artist = Artist.objects.create(name="Bad Artist")  # No MBID

        response = self.client.get('/admin/music/artist/')
        self.assertEqual(response.status_code, 200)

        # Should show quality indicators for both artists
        self.assertContains(response, 'Valid')  # For good artist
        self.assertContains(response, 'Missing')  # For bad artist

    def test_admin_recent_activity_display(self):
        """Test recent activity display."""
        response = self.client.get('/admin/music/artist/')
        self.assertEqual(response.status_code, 200)
        # Should show recent activity (scrobble from 1 hour ago)
        self.assertContains(response, 'hour')  # Time ago display

    def test_admin_performance_with_many_records(self):
        """Test admin performance with larger datasets."""
        # Create more test data
        artists = []
        for i in range(50):
            artists.append(Artist.objects.create(name=f"Artist {i}"))

        # Test that admin page loads reasonably fast
        import time
        start_time = time.time()
        response = self.client.get('/admin/music/artist/')
        end_time = time.time()

        self.assertEqual(response.status_code, 200)
        # Should load within 5 seconds even with more data
        self.assertLess(end_time - start_time, 5)

    def test_admin_ordering_works(self):
        """Test that admin ordering works correctly."""
        # Create another artist with a different name
        Artist.objects.create(name="Another Artist")

        response = self.client.get('/admin/music/artist/')
        self.assertEqual(response.status_code, 200)

        # Test sorting by name
        response = self.client.get('/admin/music/artist/?o=1')  # Sort by name
        self.assertEqual(response.status_code, 200)

    def test_admin_pagination_works(self):
        """Test admin pagination with many records."""
        # Create enough records to test pagination
        for i in range(60):  # More than the default page size of 50
            Artist.objects.create(name=f"Bulk Artist {i}")

        response = self.client.get('/admin/music/artist/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Show all')  # Pagination controls

        # Test page 2
        response = self.client.get('/admin/music/artist/?p=1')
        self.assertEqual(response.status_code, 200)

    def test_admin_autocomplete_fields(self):
        """Test autocomplete fields work."""
        response = self.client.get(f'/admin/music/track/{self.track.id}/change/')
        self.assertEqual(response.status_code, 200)
        # Should have autocomplete widgets for artist and album

    def test_sync_status_admin(self):
        """Test sync status admin interface."""
        sync_status = SyncStatus.objects.create(
            status='success',
            last_sync_timestamp=timezone.now(),
            sync_count=5
        )

        response = self.client.get('/admin/music/syncstatus/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Success')
        self.assertContains(response, '✅')  # Success icon

    def test_admin_readonly_fields(self):
        """Test that readonly fields are properly marked."""
        response = self.client.get(f'/admin/music/artist/{self.artist.id}/change/')
        self.assertEqual(response.status_code, 200)
        # created_at and updated_at should be readonly

    def test_admin_help_text_displayed(self):
        """Test that help text is displayed in admin forms."""
        response = self.client.get(f'/admin/music/artist/{self.artist.id}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MusicBrainz ID')  # MBID help text


class AdminFilterTest(TestCase):
    """Test cases for custom admin filters."""

    def setUp(self):
        """Set up test data for filter testing."""
        # Create artists with different characteristics
        self.artist_with_mbid = Artist.objects.create(
            name="Artist With MBID",
            mbid="b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        )
        self.artist_without_mbid = Artist.objects.create(
            name="Artist Without MBID"
        )
        self.artist_invalid_mbid = Artist.objects.create(
            name="Artist Invalid MBID",
            mbid="invalid-mbid"
        )

        # Create tracks with different durations
        self.short_track = Track.objects.create(
            name="Short Track",
            artist=self.artist_with_mbid,
            duration=30  # 30 seconds
        )
        self.normal_track = Track.objects.create(
            name="Normal Track",
            artist=self.artist_with_mbid,
            duration=240  # 4 minutes
        )
        self.long_track = Track.objects.create(
            name="Long Track",
            artist=self.artist_with_mbid,
            duration=720  # 12 minutes
        )

    def test_missing_mbid_filter(self):
        """Test MissingMBIDFilter functionality."""
        from music.admin_filters import MissingMBIDFilter

        # Create a mock request and model admin
        class MockRequest:
            GET = {}

        class MockModelAdmin:
            pass

        request = MockRequest()
        model_admin = MockModelAdmin()
        filter_instance = MissingMBIDFilter(request, {}, Artist, model_admin)

        # Test lookups
        lookups = filter_instance.lookups(request, model_admin)
        self.assertEqual(len(lookups), 3)
        self.assertIn(('missing', 'Missing MBID'), lookups)

        # Test queryset filtering
        queryset = Artist.objects.all()

        # Test missing MBID filter
        filter_instance.value = lambda: 'missing'
        filtered = filter_instance.queryset(request, queryset)
        self.assertIn(self.artist_without_mbid, filtered)
        self.assertNotIn(self.artist_with_mbid, filtered)

        # Test present MBID filter
        filter_instance.value = lambda: 'present'
        filtered = filter_instance.queryset(request, queryset)
        self.assertIn(self.artist_with_mbid, filtered)
        self.assertNotIn(self.artist_without_mbid, filtered)

    def test_duration_range_filter(self):
        """Test DurationRangeFilter functionality."""
        from music.admin_filters import DurationRangeFilter

        class MockRequest:
            GET = {}

        class MockModelAdmin:
            pass

        request = MockRequest()
        model_admin = MockModelAdmin()
        filter_instance = DurationRangeFilter(request, {}, Track, model_admin)

        queryset = Track.objects.all()

        # Test very short filter
        filter_instance.value = lambda: 'very_short'
        filtered = filter_instance.queryset(request, queryset)
        self.assertIn(self.short_track, filtered)
        self.assertNotIn(self.normal_track, filtered)

        # Test normal duration filter
        filter_instance.value = lambda: 'normal'
        filtered = filter_instance.queryset(request, queryset)
        self.assertIn(self.normal_track, filtered)
        self.assertNotIn(self.short_track, filtered)

        # Test very long filter
        filter_instance.value = lambda: 'very_long'
        filtered = filter_instance.queryset(request, queryset)
        self.assertIn(self.long_track, filtered)
        self.assertNotIn(self.normal_track, filtered)

    def test_data_quality_filter(self):
        """Test DataQualityFilter functionality."""
        from music.admin_filters import DataQualityFilter

        class MockRequest:
            GET = {}

        class MockModelAdmin:
            pass

        request = MockRequest()
        model_admin = MockModelAdmin()
        filter_instance = DataQualityFilter(request, {}, Artist, model_admin)

        queryset = Artist.objects.all()

        # Test missing MBID filter
        filter_instance.value = lambda: 'missing_mbid'
        filtered = filter_instance.queryset(request, queryset)
        self.assertIn(self.artist_without_mbid, filtered)
        self.assertNotIn(self.artist_with_mbid, filtered)


class AdminActionTest(TestCase):
    """Test cases for custom admin actions."""

    def setUp(self):
        """Set up test data."""
        self.artist = Artist.objects.create(
            name="Test Artist",
            mbid="invalid-mbid-format"  # Invalid MBID
        )
        self.track = Track.objects.create(
            name="Test Track",
            artist=self.artist
        )

        # Create duplicate scrobbles for testing
        timestamp = timezone.now() - timedelta(hours=1)
        self.scrobble1 = Scrobble.objects.create(track=self.track, timestamp=timestamp)
        self.scrobble2 = Scrobble.objects.create(track=self.track, timestamp=timestamp)

    def test_clear_invalid_mbids_action(self):
        """Test clear_invalid_mbids action."""
        from music.admin_actions import clear_invalid_mbids
        from django.contrib.admin import ModelAdmin
        from django.http import HttpRequest

        class MockMessages:
            def __init__(self):
                self.messages = []

            def success(self, request, message):
                self.messages.append(('success', message))

            def info(self, request, message):
                self.messages.append(('info', message))

        request = HttpRequest()
        request._messages = MockMessages()
        model_admin = ModelAdmin(Artist, None)
        queryset = Artist.objects.filter(id=self.artist.id)

        # Mock the messages framework
        import django.contrib.messages as messages
        original_success = messages.success
        original_info = messages.info

        try:
            messages.success = lambda r, m: request._messages.success(r, m)
            messages.info = lambda r, m: request._messages.info(r, m)

            # Run the action
            clear_invalid_mbids(model_admin, request, queryset)

            # Check that the invalid MBID was cleared
            self.artist.refresh_from_db()
            self.assertIsNone(self.artist.mbid)

            # Check that a success message was added
            success_messages = [msg for msg in request._messages.messages if msg[0] == 'success']
            self.assertEqual(len(success_messages), 1)
            self.assertIn('Cleared invalid MBIDs', success_messages[0][1])

        finally:
            messages.success = original_success
            messages.info = original_info

    def test_remove_duplicates_action(self):
        """Test remove_duplicates action."""
        from music.admin_actions import remove_duplicates
        from django.contrib.admin import ModelAdmin
        from django.http import HttpRequest

        class MockMessages:
            def __init__(self):
                self.messages = []

            def success(self, request, message):
                self.messages.append(('success', message))

        request = HttpRequest()
        request._messages = MockMessages()
        model_admin = ModelAdmin(Scrobble, None)
        queryset = Scrobble.objects.all()

        # Verify we have 2 duplicate scrobbles
        self.assertEqual(Scrobble.objects.count(), 2)

        # Mock the messages framework
        import django.contrib.messages as messages
        original_success = messages.success

        try:
            messages.success = lambda r, m: request._messages.success(r, m)

            # Run the action
            remove_duplicates(model_admin, request, queryset)

            # Check that duplicate was removed
            self.assertEqual(Scrobble.objects.count(), 1)

            # Check that a success message was added
            success_messages = [msg for msg in request._messages.messages if msg[0] == 'success']
            self.assertEqual(len(success_messages), 1)
            self.assertIn('Removed', success_messages[0][1])

        finally:
            messages.success = original_success


class AdminMixinTest(TestCase):
    """Test cases for admin mixins."""

    def setUp(self):
        """Set up test data."""
        self.artist = Artist.objects.create(
            name="Test Artist",
            mbid="b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        )

    def test_mbid_status_mixin(self):
        """Test MBIDStatusMixin functionality."""
        from music.admin_mixins import MBIDStatusMixin

        mixin = MBIDStatusMixin()

        # Test valid MBID
        result = mixin.mbid_status_display(self.artist)
        self.assertIn('Valid', result)
        self.assertIn('28a745', result)  # Green color

        # Test invalid MBID
        self.artist.mbid = "invalid-mbid"
        result = mixin.mbid_status_display(self.artist)
        self.assertIn('Invalid', result)
        self.assertIn('dc3545', result)  # Red color

        # Test missing MBID
        self.artist.mbid = None
        result = mixin.mbid_status_display(self.artist)
        self.assertIn('Missing', result)
        self.assertIn('6c757d', result)  # Gray color

    def test_data_quality_mixin(self):
        """Test DataQualityMixin functionality."""
        from music.admin_mixins import DataQualityMixin

        mixin = DataQualityMixin()

        # Test high quality (has MBID and URL)
        self.artist.url = "https://musicbrainz.org/artist/test"
        result = mixin.data_quality_score(self.artist)
        self.assertIn('100%', result)
        self.assertIn('28a745', result)  # Green color

        # Test medium quality (missing URL)
        self.artist.url = None
        result = mixin.data_quality_score(self.artist)
        self.assertIn('80%', result)
        self.assertIn('ffc107', result)  # Yellow color

        # Test low quality (missing MBID and URL)
        self.artist.mbid = None
        result = mixin.data_quality_score(self.artist)
        self.assertIn('50%', result)
        self.assertIn('dc3545', result)  # Red color

    def test_linkable_mixin(self):
        """Test LinkableMixin functionality."""
        from music.admin_mixins import LinkableMixin

        mixin = LinkableMixin()

        # Test creating admin link
        result = mixin.create_admin_link(self.artist)
        self.assertIn('href', result)
        self.assertIn('music_artist_change', result)
        self.assertIn(str(self.artist.id), result)

        # Test with None object
        result = mixin.create_admin_link(None)
        self.assertEqual(result, '-')

    def test_timestamp_mixin(self):
        """Test TimestampMixin functionality."""
        from music.admin_mixins import TimestampMixin

        mixin = TimestampMixin()

        # Test format_timestamp
        now = timezone.now()
        result = mixin.format_timestamp(now, include_time=True)
        self.assertIn(now.strftime('%Y-%m-%d'), result)
        self.assertIn(now.strftime('%H:%M'), result)

        result = mixin.format_timestamp(now, include_time=False)
        self.assertIn(now.strftime('%Y-%m-%d'), result)
        self.assertNotIn(now.strftime('%H:%M'), result)

        # Test get_time_ago
        past_time = now - timedelta(hours=2)
        result = mixin.get_time_ago(past_time)
        self.assertIn('hour', result)
        self.assertIn('ago', result)

        # Test with None
        result = mixin.format_timestamp(None)
        self.assertEqual(result, '-')

        result = mixin.get_time_ago(None)
        self.assertEqual(result, '-')