"""
Tests for the calculate_stats management command.
"""

import json
import tempfile
from io import StringIO
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone

from music.models import Artist, Album, Track, Scrobble


class CalculateStatsCommandTest(TestCase):
    """Test cases for the calculate_stats management command."""

    def setUp(self):
        """Set up test data."""
        # Create test artists
        self.artist1 = Artist.objects.create(
            name="Test Artist 1",
            mbid="12345678-1234-1234-1234-123456789012"
        )
        self.artist2 = Artist.objects.create(
            name="Test Artist 2"  # No MBID
        )
        self.artist3 = Artist.objects.create(
            name="Test Artist 3",
            mbid="87654321-4321-4321-4321-210987654321"
        )

        # Create test albums
        self.album1 = Album.objects.create(
            name="Test Album 1",
            artist=self.artist1,
            mbid="11111111-1111-1111-1111-111111111111"
        )
        self.album2 = Album.objects.create(
            name="Test Album 2",
            artist=self.artist2  # No MBID
        )

        # Create test tracks
        self.track1 = Track.objects.create(
            name="Track 1",
            artist=self.artist1,
            album=self.album1,
            mbid="33333333-3333-3333-3333-333333333333",
            duration=180
        )
        self.track2 = Track.objects.create(
            name="Track 2",
            artist=self.artist1,
            album=self.album1,
            duration=240
        )
        self.track3 = Track.objects.create(
            name="Track 3",
            artist=self.artist2,
            album=self.album2,
            duration=200
        )
        self.track4 = Track.objects.create(
            name="Track 4",
            artist=self.artist3,
            album=None,  # No album
            duration=150
        )

        # Create test scrobbles with specific timestamps for predictable testing
        base_time = timezone.now().replace(year=2023, month=6, day=15, hour=12, minute=0, second=0, microsecond=0)

        self.scrobbles = []

        # Artist 1: 10 scrobbles (most played)
        for i in range(5):
            scrobble = Scrobble.objects.create(
                track=self.track1,
                timestamp=base_time + timedelta(days=i)
            )
            self.scrobbles.append(scrobble)

        for i in range(5):
            scrobble = Scrobble.objects.create(
                track=self.track2,
                timestamp=base_time + timedelta(days=i+10)
            )
            self.scrobbles.append(scrobble)

        # Artist 2: 3 scrobbles
        for i in range(3):
            scrobble = Scrobble.objects.create(
                track=self.track3,
                timestamp=base_time + timedelta(days=i+20)
            )
            self.scrobbles.append(scrobble)

        # Artist 3: 2 scrobbles (least played)
        for i in range(2):
            scrobble = Scrobble.objects.create(
                track=self.track4,
                timestamp=base_time + timedelta(days=i+30)
            )
            self.scrobbles.append(scrobble)

        # Add some scrobbles in different years for time analysis
        old_scrobble = Scrobble.objects.create(
            track=self.track1,
            timestamp=base_time.replace(year=2022, month=1, day=1)
        )
        self.scrobbles.append(old_scrobble)

        new_scrobble = Scrobble.objects.create(
            track=self.track1,
            timestamp=base_time.replace(year=2024, month=12, day=31)
        )
        self.scrobbles.append(new_scrobble)

    def test_basic_counts_calculation(self):
        """Test basic count statistics."""
        out = StringIO()
        call_command('calculate_stats', '--category=counts', stdout=out)
        output = out.getvalue()

        # Check that basic counts are present
        self.assertIn('Total Scrobbles: 17', output)  # 15 + 2 extra scrobbles
        self.assertIn('Unique Tracks: 4', output)
        self.assertIn('Unique Artists: 3', output)
        self.assertIn('Unique Albums: 2', output)  # track4 has no album

    def test_top_items_calculation(self):
        """Test top items analysis."""
        out = StringIO()
        call_command('calculate_stats', '--category=top-items', '--top-n=3', stdout=out)
        output = out.getvalue()

        # Check that top artists are correctly identified
        # Artist 1 should have the most plays (12 total: 5+5+1+1)
        self.assertIn('Test Artist 1', output)

        # Check MBID indicators
        self.assertIn('✓', output)  # Should have MBID indicators
        self.assertIn('✗', output)  # Should have no-MBID indicators

    def test_time_analysis_calculation(self):
        """Test time-based analysis."""
        out = StringIO()
        call_command('calculate_stats', '--category=time-analysis', stdout=out)
        output = out.getvalue()

        # Should have date range information
        self.assertIn('Date Range:', output)
        self.assertIn('2022', output)  # Should include the old scrobble year
        self.assertIn('2024', output)  # Should include the new scrobble year

        # Should have yearly breakdown
        self.assertIn('Yearly Breakdown:', output)

    def test_data_quality_calculation(self):
        """Test data quality metrics."""
        out = StringIO()
        call_command('calculate_stats', '--category=data-quality', stdout=out)
        output = out.getvalue()

        # Should have MBID coverage information
        self.assertIn('MBID Coverage:', output)
        self.assertIn('Artists:', output)
        self.assertIn('Albums:', output)
        self.assertIn('Tracks:', output)

        # Should have missing data information
        self.assertIn('Missing Data:', output)
        self.assertIn('Tracks without Album: 1', output)  # track4 has no album

    def test_date_filtering(self):
        """Test date filtering functionality."""
        out = StringIO()
        call_command(
            'calculate_stats',
            '--category=counts',
            '--from-date=2023-01-01',
            '--to-date=2023-12-31',
            stdout=out
        )
        output = out.getvalue()

        # Should only count scrobbles from 2023
        # Excludes: 1 from 2022, 1 from 2024 = 15 total
        self.assertIn('Total Scrobbles: 15', output)

    def test_json_output_format(self):
        """Test JSON output format."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_file:
            call_command(
                'calculate_stats',
                '--category=counts',
                '--output-format=json',
                '--output-file=' + tmp_file.name
            )

            # Read the JSON output
            with open(tmp_file.name, 'r') as f:
                data = json.load(f)

            # Verify JSON structure
            self.assertIn('generated_at', data)
            self.assertIn('filters', data)
            self.assertIn('statistics', data)

            # Verify statistics data
            stats = data['statistics']
            self.assertIn('basic_counts', stats)

            basic_counts = stats['basic_counts']
            self.assertEqual(basic_counts['total_scrobbles'], 17)
            self.assertEqual(basic_counts['unique_tracks'], 4)
            self.assertEqual(basic_counts['unique_artists'], 3)

    def test_invalid_date_format(self):
        """Test error handling for invalid date formats."""
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            out = StringIO()
            err = StringIO()
            call_command(
                'calculate_stats',
                '--from-date=invalid-date',
                stdout=out,
                stderr=err
            )

    def test_empty_dataset(self):
        """Test behavior with empty dataset."""
        # Clear all scrobbles
        Scrobble.objects.all().delete()

        out = StringIO()
        call_command('calculate_stats', '--category=counts', stdout=out)
        output = out.getvalue()

        # Should handle empty dataset gracefully
        self.assertIn('Total Scrobbles: 0', output)
        self.assertIn('Unique Tracks: 0', output)

    def test_top_n_parameter(self):
        """Test the top-n parameter functionality."""
        out = StringIO()
        call_command('calculate_stats', '--category=top-items', '--top-n=2', stdout=out)
        output = out.getvalue()

        # Should only show top 2 items
        lines = output.split('\n')
        artist_lines = [line for line in lines if line.strip().startswith(('1.', '2.', '3.'))]

        # Should have exactly 2 entries per category (artists, albums, tracks)
        # That's 6 total numbered lines
        self.assertEqual(len(artist_lines), 6)  # 2 artists + 2 albums + 2 tracks

    def test_all_categories_combined(self):
        """Test running all categories together."""
        out = StringIO()
        call_command('calculate_stats', '--category=all', stdout=out)
        output = out.getvalue()

        # Should contain all sections
        self.assertIn('Basic Counts:', output)
        self.assertIn('Top', output)  # Top artists/albums/tracks
        self.assertIn('Time Analysis:', output)
        self.assertIn('Data Quality:', output)

    def test_verbosity_levels(self):
        """Test different verbosity levels."""
        # Test with verbosity 0 (quiet)
        out = StringIO()
        call_command('calculate_stats', '--category=counts', '--verbosity=0', stdout=out)
        output = out.getvalue()

        # Should still have the main output but no progress messages
        self.assertIn('Total Scrobbles:', output)
        self.assertNotIn('Calculating statistics...', output)

        # Test with verbosity 2 (verbose)
        out = StringIO()
        call_command('calculate_stats', '--category=counts', '--verbosity=2', stdout=out)
        output = out.getvalue()

        # Should have progress messages
        self.assertIn('Calculating statistics...', output)
        self.assertIn('Calculating basic counts...', output)

    def test_performance_with_large_dataset(self):
        """Test performance characteristics (should complete quickly even with more data)."""
        # Add more test data
        base_time = timezone.now()
        bulk_scrobbles = []

        for i in range(100):
            bulk_scrobbles.append(Scrobble(
                track=self.track1,
                timestamp=base_time + timedelta(minutes=i)
            ))

        Scrobble.objects.bulk_create(bulk_scrobbles)

        # Time the command execution
        import time
        start_time = time.time()

        out = StringIO()
        call_command('calculate_stats', '--category=all', stdout=out)

        execution_time = time.time() - start_time

        # Should complete in reasonable time (less than 5 seconds)
        self.assertLess(execution_time, 5.0)

        # Verify correct count
        output = out.getvalue()
        self.assertIn('Total Scrobbles: 117', output)  # 17 original + 100 new

    def test_mbid_percentage_calculation(self):
        """Test MBID percentage calculations."""
        out = StringIO()
        call_command('calculate_stats', '--category=data-quality', stdout=out)
        output = out.getvalue()

        # With our test data:
        # Artists: 2 out of 3 have MBIDs = 66.7%
        # Albums: 1 out of 2 have MBIDs = 50.0%
        # Tracks: 1 out of 4 have MBIDs = 25.0%

        self.assertIn('Artists: 66.7%', output)
        self.assertIn('Albums: 50.0%', output)
        self.assertIn('Tracks: 25.0%', output)

    def test_duration_formatting_in_top_tracks(self):
        """Test that track durations are properly formatted."""
        out = StringIO()
        call_command('calculate_stats', '--category=top-items', '--top-n=1', stdout=out)
        output = out.getvalue()

        # Should show duration in MM:SS format
        # track1 has duration=180 seconds = 3:00
        self.assertIn('(3:00)', output)


class CalculateStatsIntegrationTest(TestCase):
    """Integration tests for the calculate_stats command with realistic scenarios."""

    def test_realistic_listening_patterns(self):
        """Test with realistic listening patterns across multiple years."""
        # Create a realistic dataset spanning multiple years
        artist = Artist.objects.create(name="Favorite Band", mbid="test-mbid-123")
        album = Album.objects.create(name="Great Album", artist=artist, mbid="album-mbid-123")
        track1 = Track.objects.create(name="Hit Song", artist=artist, album=album, duration=200)
        track2 = Track.objects.create(name="Deep Cut", artist=artist, album=album, duration=180)

        # Simulate listening patterns
        base_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        scrobbles = []

        # Heavy listening in 2020 (pandemic year)
        for day in range(100):
            scrobbles.append(Scrobble(
                track=track1,
                timestamp=base_date + timedelta(days=day)
            ))

        # Moderate listening in 2021-2022
        for month in range(12):
            for week in range(2):
                scrobbles.append(Scrobble(
                    track=track2,
                    timestamp=base_date.replace(year=2021) + timedelta(days=month*30 + week*7)
                ))

        # Light listening in 2023
        for month in range(6):
            scrobbles.append(Scrobble(
                track=track1,
                timestamp=base_date.replace(year=2023) + timedelta(days=month*60)
            ))

        Scrobble.objects.bulk_create(scrobbles)

        out = StringIO()
        call_command('calculate_stats', stdout=out)
        output = out.getvalue()

        # Verify realistic patterns are detected
        self.assertIn('Most Active Year: 2020', output)
        self.assertIn('Favorite Band', output)
        self.assertIn('Hit Song', output)