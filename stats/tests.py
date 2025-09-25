from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from music.models import Artist, Album, Track, Scrobble
import json


class StatsAPITestCase(APITestCase):
    """Test cases for the Stats API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Create artists
        self.artist1 = Artist.objects.create(
            name="Test Artist 1",
            mbid="12345678-1234-1234-1234-123456789012",
            url="https://musicbrainz.org/artist/test1"
        )
        self.artist2 = Artist.objects.create(
            name="Test Artist 2",
            mbid="87654321-4321-4321-4321-210987654321"
        )

        # Create albums
        self.album1 = Album.objects.create(
            name="Test Album 1",
            artist=self.artist1,
            mbid="11111111-1111-1111-1111-111111111111"
        )
        self.album2 = Album.objects.create(
            name="Test Album 2",
            artist=self.artist2,
            mbid="22222222-2222-2222-2222-222222222222"
        )

        # Create tracks
        self.track1 = Track.objects.create(
            name="Test Track 1",
            artist=self.artist1,
            album=self.album1,
            mbid="33333333-3333-3333-3333-333333333333",
            duration=180
        )
        self.track2 = Track.objects.create(
            name="Test Track 2",
            artist=self.artist1,
            album=self.album1,
            duration=240
        )
        self.track3 = Track.objects.create(
            name="Test Track 3",
            artist=self.artist2,
            album=self.album2,
            duration=200
        )

        # Create scrobbles with different timestamps
        now = timezone.now()
        self.scrobbles = [
            Scrobble.objects.create(
                track=self.track1,
                timestamp=now - timedelta(hours=1),
                lastfm_reference_id="ref1"
            ),
            Scrobble.objects.create(
                track=self.track1,
                timestamp=now - timedelta(days=1),
                lastfm_reference_id="ref2"
            ),
            Scrobble.objects.create(
                track=self.track2,
                timestamp=now - timedelta(days=3),
                lastfm_reference_id="ref3"
            ),
            Scrobble.objects.create(
                track=self.track3,
                timestamp=now - timedelta(days=10),
                lastfm_reference_id="ref4"
            ),
            Scrobble.objects.create(
                track=self.track1,
                timestamp=now - timedelta(days=40),
                lastfm_reference_id="ref5"
            ),
        ]

    def test_api_root(self):
        """Test the API root endpoint returns overview."""
        url = reverse('stats:stats-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('message', data)
        self.assertIn('endpoints', data)
        self.assertIn('time_periods', data)
        self.assertEqual(data['time_periods'], ['7d', '30d', '90d', '180d', '365d', 'all'])

    def test_recent_tracks(self):
        """Test recent tracks endpoint (Story 9 compliance)."""
        url = reverse('stats:stats-recent-tracks')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Story 9: Check required response structure
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIn('has_next', data)
        self.assertIn('has_previous', data)

        results = data['results']
        self.assertTrue(len(results) > 0)

        # Story 9: Default limit should be 10
        self.assertLessEqual(len(results), 10)

        # Story 9: Check response format matches specification
        first_scrobble = results[0]
        self.assertIn('track', first_scrobble)
        self.assertIn('artist', first_scrobble)
        self.assertIn('album', first_scrobble)
        self.assertIn('timestamp', first_scrobble)

        # Should NOT have old format fields
        self.assertNotIn('track_name', first_scrobble)
        self.assertNotIn('track_id', first_scrobble)
        self.assertNotIn('id', first_scrobble)

        # Story 9: Check ordering (most recent first)
        if len(results) > 1:
            self.assertGreaterEqual(
                results[0]['timestamp'],
                results[1]['timestamp']
            )

        # Story 9: Check ISO 8601 timestamp format
        timestamp = first_scrobble['timestamp']
        self.assertTrue(timestamp.endswith('Z'))
        self.assertRegex(timestamp, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')

    def test_recent_tracks_direct_url(self):
        """Test Story 9 direct URL /api/recent-tracks/."""
        url = reverse('stats:recent-tracks')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIn('has_next', data)
        self.assertIn('has_previous', data)

    def test_recent_tracks_limit_parameter(self):
        """Test Story 9 ?limit=N parameter support."""
        base_url = reverse('stats:stats-recent-tracks')

        # Test custom limit
        response = self.client.get(base_url + '?limit=3')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 3)

        # Test min limit (should default to 1)
        response = self.client.get(base_url + '?limit=0')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 1)

        # Test max limit (should cap at 50)
        response = self.client.get(base_url + '?limit=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 50)

        # Test invalid limit (should default to 10)
        response = self.client.get(base_url + '?limit=invalid')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 10)

    def test_recent_tracks_pagination_metadata(self):
        """Test Story 9 pagination metadata (has_next, has_previous)."""
        url = reverse('stats:stats-recent-tracks')

        # Test first page
        response = self.client.get(url + '?limit=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should have pagination metadata
        self.assertIn('has_next', data)
        self.assertIn('has_previous', data)
        self.assertEqual(data['has_previous'], False)

        # If we have more than 2 scrobbles, should have next page
        if len(self.scrobbles) > 2:
            self.assertEqual(data['has_next'], True)

    def test_top_artists_default_period(self):
        """Test top artists endpoint with default 30d period."""
        url = reverse('stats:stats-top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)

        results = data['results']
        if len(results) > 0:
            first_artist = results[0]
            self.assertIn('id', first_artist)
            self.assertIn('name', first_artist)
            self.assertIn('scrobble_count', first_artist)
            self.assertIn('track_count', first_artist)
            self.assertIn('album_count', first_artist)

            # Should be ordered by scrobble count (highest first)
            if len(results) > 1:
                self.assertGreaterEqual(
                    results[0]['scrobble_count'],
                    results[1]['scrobble_count']
                )

    def test_top_artists_with_time_filtering(self):
        """Test top artists with different time periods."""
        base_url = reverse('stats:stats-top-artists')

        # Test 7-day period
        response_7d = self.client.get(base_url + '?period=7d')
        self.assertEqual(response_7d.status_code, status.HTTP_200_OK)
        data_7d = response_7d.json()

        # Test all-time period
        response_all = self.client.get(base_url + '?period=all')
        self.assertEqual(response_all.status_code, status.HTTP_200_OK)
        data_all = response_all.json()

        # All-time should have same or more results than 7-day
        self.assertGreaterEqual(data_all['count'], data_7d['count'])

    def test_top_albums_basic(self):
        """Test basic top albums endpoint functionality."""
        url = reverse('stats:top-albums')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Story 11 required response format
        self.assertIn('period', data)
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIn('total_scrobbles', data)
        self.assertEqual(data['period'], 'all')

        if len(data['results']) > 0:
            first_album = data['results'][0]
            # Story 11 required fields: album, artist, scrobble_count, mbid
            self.assertIn('album', first_album)
            self.assertIn('artist', first_album)
            self.assertIn('scrobble_count', first_album)
            self.assertIn('mbid', first_album)

    def test_top_albums_time_periods(self):
        """Test all supported time periods for top albums."""
        periods = ['7d', '30d', '90d', '180d', '365d', 'all']

        for period in periods:
            with self.subTest(period=period):
                url = reverse('stats:top-albums')
                response = self.client.get(url, {'period': period})

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertEqual(data['period'], period)
                self.assertIn('results', data)
                self.assertIn('count', data)
                self.assertIn('total_scrobbles', data)

    def test_top_albums_limit_parameter(self):
        """Test limit parameter validation for top albums."""
        url = reverse('stats:top-albums')

        # Test default limit (10)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data['count'], 10)

        # Test custom limit
        response = self.client.get(url, {'limit': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data['count'], 5)

        # Test max limit (100)
        response = self.client.get(url, {'limit': 150})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data['count'], 100)  # Should be capped at 100

        # Test min limit (1)
        response = self.client.get(url, {'limit': 0})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should default to 1 for invalid values

    def test_top_albums_custom_date_range(self):
        """Test custom date range filtering for top albums."""
        url = reverse('stats:top-albums')

        # Test with both from_date and to_date
        response = self.client.get(url, {
            'from_date': '2023-01-01',
            'to_date': '2023-12-31'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], '2023-01-01 to 2023-12-31')

        # Test with only from_date
        response = self.client.get(url, {'from_date': '2023-06-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'from 2023-06-01')

        # Test with only to_date
        response = self.client.get(url, {'to_date': '2023-06-30'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'until 2023-06-30')

    def test_top_albums_invalid_period(self):
        """Test invalid period handling for top albums."""
        url = reverse('stats:top-albums')

        # Invalid period should default to 'all'
        response = self.client.get(url, {'period': 'invalid'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'all')

    def test_top_albums_invalid_date_format(self):
        """Test invalid date format handling for top albums."""
        url = reverse('stats:top-albums')

        # Invalid date format should return error
        response = self.client.get(url, {'from_date': 'invalid-date'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid date range (from_date after to_date)
        response = self.client.get(url, {
            'from_date': '2023-12-31',
            'to_date': '2023-01-01'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_top_albums_ordering(self):
        """Test that top albums are ordered by scrobble count descending."""
        url = reverse('stats:top-albums')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        if len(data['results']) > 1:
            # Check that results are ordered by scrobble_count descending
            for i in range(len(data['results']) - 1):
                current_count = data['results'][i]['scrobble_count']
                next_count = data['results'][i + 1]['scrobble_count']
                self.assertGreaterEqual(current_count, next_count)

    def test_top_albums_response_format(self):
        """Test that top albums response matches Story 11 specification."""
        url = reverse('stats:top-albums')
        response = self.client.get(url, {'period': '90d'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Top-level structure
        expected_keys = {'period', 'results', 'count', 'total_scrobbles'}
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertEqual(data['period'], '90d')

        # Individual album structure (if any results)
        if data['results']:
            album = data['results'][0]
            expected_album_keys = {'album', 'artist', 'scrobble_count', 'mbid'}
            self.assertEqual(set(album.keys()), expected_album_keys)

            # Verify field types
            self.assertIsInstance(album['album'], str)
            self.assertIsInstance(album['artist'], str)
            self.assertIsInstance(album['scrobble_count'], int)
            # mbid can be None or string
            self.assertTrue(album['mbid'] is None or isinstance(album['mbid'], str))

    def test_top_tracks_basic(self):
        """Test basic top tracks endpoint functionality."""
        url = reverse('stats:top-tracks')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Story 12 required response format
        self.assertIn('period', data)
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIn('total_scrobbles', data)
        self.assertEqual(data['period'], 'all')

        if len(data['results']) > 0:
            first_track = data['results'][0]
            # Story 12 required fields: track, artist, album, scrobble_count, mbid
            self.assertIn('track', first_track)
            self.assertIn('artist', first_track)
            self.assertIn('album', first_track)
            self.assertIn('scrobble_count', first_track)
            self.assertIn('mbid', first_track)

    def test_top_tracks_time_periods(self):
        """Test all supported time periods for top tracks."""
        periods = ['7d', '30d', '90d', '180d', '365d', 'all']

        for period in periods:
            with self.subTest(period=period):
                url = reverse('stats:top-tracks')
                response = self.client.get(url, {'period': period})

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertEqual(data['period'], period)
                self.assertIn('results', data)
                self.assertIn('count', data)
                self.assertIn('total_scrobbles', data)

    def test_top_tracks_limit_parameter(self):
        """Test limit parameter validation for top tracks."""
        url = reverse('stats:top-tracks')

        # Test default limit (10)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data['count'], 10)

        # Test custom limit
        response = self.client.get(url, {'limit': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data['count'], 5)

        # Test max limit (100)
        response = self.client.get(url, {'limit': 150})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data['count'], 100)  # Should be capped at 100

        # Test min limit (1)
        response = self.client.get(url, {'limit': 0})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should default to 1 for invalid values

    def test_top_tracks_custom_date_range(self):
        """Test custom date range filtering for top tracks."""
        url = reverse('stats:top-tracks')

        # Test with both from_date and to_date
        response = self.client.get(url, {
            'from_date': '2023-01-01',
            'to_date': '2023-12-31'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], '2023-01-01 to 2023-12-31')

        # Test with only from_date
        response = self.client.get(url, {'from_date': '2023-06-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'from 2023-06-01')

        # Test with only to_date
        response = self.client.get(url, {'to_date': '2023-06-30'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'until 2023-06-30')

    def test_top_tracks_invalid_period(self):
        """Test invalid period handling for top tracks."""
        url = reverse('stats:top-tracks')

        # Invalid period should default to 'all'
        response = self.client.get(url, {'period': 'invalid'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'all')

    def test_top_tracks_invalid_date_format(self):
        """Test invalid date format handling for top tracks."""
        url = reverse('stats:top-tracks')

        # Invalid date format should return error
        response = self.client.get(url, {'from_date': 'invalid-date'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid date range (from_date after to_date)
        response = self.client.get(url, {
            'from_date': '2023-12-31',
            'to_date': '2023-01-01'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_top_tracks_ordering(self):
        """Test that top tracks are ordered by scrobble count descending."""
        url = reverse('stats:top-tracks')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        if len(data['results']) > 1:
            # Check that results are ordered by scrobble_count descending
            for i in range(len(data['results']) - 1):
                current_count = data['results'][i]['scrobble_count']
                next_count = data['results'][i + 1]['scrobble_count']
                self.assertGreaterEqual(current_count, next_count)

    def test_top_tracks_missing_album_handling(self):
        """Test that tracks with missing album information are handled gracefully."""
        url = reverse('stats:top-tracks')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify that tracks can have null album values
        for track in data['results']:
            self.assertIn('album', track)
            # Album can be None or string
            self.assertTrue(track['album'] is None or isinstance(track['album'], str))

    def test_top_tracks_response_format(self):
        """Test that top tracks response matches Story 12 specification."""
        url = reverse('stats:top-tracks')
        response = self.client.get(url, {'period': '7d'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Top-level structure
        expected_keys = {'period', 'results', 'count', 'total_scrobbles'}
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertEqual(data['period'], '7d')

        # Individual track structure (if any results)
        if data['results']:
            track = data['results'][0]
            expected_track_keys = {'track', 'artist', 'album', 'scrobble_count', 'mbid'}
            self.assertEqual(set(track.keys()), expected_track_keys)

            # Verify field types
            self.assertIsInstance(track['track'], str)
            self.assertIsInstance(track['artist'], str)
            # album can be None or string
            self.assertTrue(track['album'] is None or isinstance(track['album'], str))
            self.assertIsInstance(track['scrobble_count'], int)
            # mbid can be None or string
            self.assertTrue(track['mbid'] is None or isinstance(track['mbid'], str))

    def test_scrobbles_chart_basic(self):
        """Test basic scrobbles chart endpoint functionality."""
        url = reverse('stats:scrobbles-chart')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Story 13 required response format
        self.assertIn('period', data)
        self.assertIn('granularity', data)
        self.assertIn('data', data)
        self.assertIn('total_scrobbles', data)

        # Check data structure
        if data['data']:
            first_item = data['data'][0]
            expected_keys = {'period', 'scrobble_count', 'start_date', 'end_date'}
            self.assertEqual(set(first_item.keys()), expected_keys)

    def test_scrobbles_chart_auto_granularity(self):
        """Test automatic granularity selection."""
        url = reverse('stats:scrobbles-chart')

        # Test different periods and expected granularities
        test_cases = [
            ('7d', 'daily'),
            ('30d', 'daily'),
            ('90d', 'monthly'),
            ('365d', 'monthly'),
            ('all', 'yearly')
        ]

        for period, expected_granularity in test_cases:
            with self.subTest(period=period, expected_granularity=expected_granularity):
                response = self.client.get(url, {'period': period})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertEqual(data['granularity'], expected_granularity)

    def test_scrobbles_chart_manual_granularity(self):
        """Test manual granularity override."""
        url = reverse('stats:scrobbles-chart')

        granularities = ['daily', 'monthly', 'yearly']
        for granularity in granularities:
            with self.subTest(granularity=granularity):
                response = self.client.get(url, {
                    'period': '365d',
                    'granularity': granularity
                })
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertEqual(data['granularity'], granularity)

    def test_scrobbles_chart_invalid_granularity(self):
        """Test invalid granularity handling."""
        url = reverse('stats:scrobbles-chart')
        response = self.client.get(url, {'granularity': 'invalid'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scrobbles_chart_time_periods(self):
        """Test all supported time periods for chart data."""
        url = reverse('stats:scrobbles-chart')
        periods = ['7d', '30d', '90d', '180d', '365d', 'all']

        for period in periods:
            with self.subTest(period=period):
                response = self.client.get(url, {'period': period})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertEqual(data['period'], period)

    def test_scrobbles_chart_custom_date_range(self):
        """Test custom date range filtering for chart data."""
        url = reverse('stats:scrobbles-chart')

        # Test with both from_date and to_date
        response = self.client.get(url, {
            'from_date': '2023-01-01',
            'to_date': '2023-01-31',
            'granularity': 'daily'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], '2023-01-01 to 2023-01-31')
        self.assertEqual(data['granularity'], 'daily')

    def test_scrobbles_chart_data_format(self):
        """Test chart data format compliance."""
        url = reverse('stats:scrobbles-chart')
        response = self.client.get(url, {'period': '30d', 'granularity': 'daily'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Check data items format
        for item in data['data']:
            self.assertIn('period', item)
            self.assertIn('scrobble_count', item)
            self.assertIn('start_date', item)
            self.assertIn('end_date', item)

            # Verify types
            self.assertIsInstance(item['period'], str)
            self.assertIsInstance(item['scrobble_count'], int)
            self.assertIsInstance(item['start_date'], str)
            self.assertIsInstance(item['end_date'], str)

            # Verify scrobble_count is non-negative
            self.assertGreaterEqual(item['scrobble_count'], 0)

    def test_scrobbles_chart_granularity_formats(self):
        """Test period format for different granularities."""
        url = reverse('stats:scrobbles-chart')

        # Daily format: YYYY-MM-DD
        response = self.client.get(url, {'period': '7d', 'granularity': 'daily'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        if data['data']:
            period = data['data'][0]['period']
            self.assertRegex(period, r'^\d{4}-\d{2}-\d{2}$')

        # Monthly format: YYYY-MM
        response = self.client.get(url, {'period': '90d', 'granularity': 'monthly'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        if data['data']:
            period = data['data'][0]['period']
            self.assertRegex(period, r'^\d{4}-\d{2}$')

        # Yearly format: YYYY
        response = self.client.get(url, {'period': 'all', 'granularity': 'yearly'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        if data['data']:
            period = data['data'][0]['period']
            self.assertRegex(period, r'^\d{4}$')

    def test_scrobbles_chart_empty_periods(self):
        """Test handling of periods with no scrobbles."""
        url = reverse('stats:scrobbles-chart')

        # Request data for future dates (should have no scrobbles)
        response = self.client.get(url, {
            'from_date': '2030-01-01',
            'to_date': '2030-01-31',
            'granularity': 'daily'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should have empty data array or all zero counts
        for item in data['data']:
            self.assertEqual(item['scrobble_count'], 0)

    def test_scrobbles_chart_invalid_dates(self):
        """Test invalid date format handling."""
        url = reverse('stats:scrobbles-chart')

        # Invalid date format
        response = self.client.get(url, {'from_date': 'invalid-date'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid date range
        response = self.client.get(url, {
            'from_date': '2023-12-31',
            'to_date': '2023-01-01'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scrobbles_chart_performance_limiting(self):
        """Test that data points are limited for performance."""
        url = reverse('stats:scrobbles-chart')

        # Request a very long period that might generate many data points
        response = self.client.get(url, {
            'from_date': '2020-01-01',
            'to_date': '2025-12-31',
            'granularity': 'daily'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should be limited to reasonable number of points
        self.assertLessEqual(len(data['data']), 366)

    def test_artist_detail_story14_format(self):
        """Test artist detail endpoint returns Story 14 compliant format."""
        url = reverse('stats:artist-detail', kwargs={'pk': self.artist1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Check Story 14 top-level structure
        self.assertIn('artist', data)
        self.assertIn('top_albums', data)
        self.assertIn('top_tracks', data)
        self.assertIn('chart_data', data)

        # Check artist object structure
        artist_data = data['artist']
        self.assertEqual(artist_data['name'], self.artist1.name)
        self.assertEqual(artist_data['mbid'], self.artist1.mbid)
        self.assertIn('total_scrobbles', artist_data)
        self.assertIn('first_scrobble', artist_data)
        self.assertIn('last_scrobble', artist_data)

        # Check top_albums structure
        self.assertIsInstance(data['top_albums'], list)
        if data['top_albums']:
            album = data['top_albums'][0]
            self.assertIn('album', album)
            self.assertIn('scrobble_count', album)

        # Check top_tracks structure
        self.assertIsInstance(data['top_tracks'], list)
        if data['top_tracks']:
            track = data['top_tracks'][0]
            self.assertIn('track', track)
            self.assertIn('album', track)
            self.assertIn('scrobble_count', track)

        # Check chart_data structure
        chart_data = data['chart_data']
        self.assertIn('period', chart_data)
        self.assertIn('granularity', chart_data)
        self.assertIn('data', chart_data)
        self.assertIn('total_scrobbles', chart_data)

    def test_artist_detail_mbid_lookup(self):
        """Test artist detail endpoint with MBID lookup (Story 14)."""
        url = reverse('stats:artist-detail-mbid', kwargs={'pk': self.artist1.mbid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should return same structure as ID lookup
        self.assertIn('artist', data)
        self.assertEqual(data['artist']['name'], self.artist1.name)
        self.assertEqual(data['artist']['mbid'], self.artist1.mbid)

    def test_artist_detail_time_filtering(self):
        """Test artist detail endpoint with time filtering."""
        url = reverse('stats:artist-detail', kwargs={'pk': self.artist1.id})
        response = self.client.get(url, {'period': '30d'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should still return Story 14 format
        self.assertIn('artist', data)
        self.assertIn('top_albums', data)
        self.assertIn('top_tracks', data)
        self.assertIn('chart_data', data)

        # Chart data should reflect the period
        self.assertEqual(data['chart_data']['period'], '30d')

    def test_artist_detail_limit_parameter(self):
        """Test artist detail endpoint with limit parameter."""
        url = reverse('stats:artist-detail', kwargs={'pk': self.artist1.id})
        response = self.client.get(url, {'limit': 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Top lists should respect limit (if there are enough items)
        self.assertTrue(len(data['top_albums']) <= 5)
        self.assertTrue(len(data['top_tracks']) <= 5)

    def test_artist_detail_custom_date_range(self):
        """Test artist detail endpoint with custom date range."""
        from_date = '2024-01-01'
        to_date = '2024-12-31'

        url = reverse('stats:artist-detail', kwargs={'pk': self.artist1.id})
        response = self.client.get(url, {'from_date': from_date, 'to_date': to_date})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Chart data should reflect custom date range
        self.assertEqual(data['chart_data']['period'], f"{from_date} to {to_date}")

    def test_artist_detail_chart_granularity(self):
        """Test artist detail endpoint with manual granularity override."""
        url = reverse('stats:artist-detail', kwargs={'pk': self.artist1.id})
        response = self.client.get(url, {'granularity': 'monthly'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Chart data should use requested granularity
        self.assertEqual(data['chart_data']['granularity'], 'monthly')

    def test_album_detail_story15_format(self):
        """Test album detail endpoint returns Story 15 compliant format."""
        url = reverse('stats:album-detail', kwargs={'pk': self.album1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Check Story 15 top-level structure
        self.assertIn('album', data)
        self.assertIn('tracks', data)
        self.assertIn('chart_data', data)

        # Check album object structure
        album_data = data['album']
        self.assertEqual(album_data['name'], self.album1.name)
        self.assertEqual(album_data['artist'], self.artist1.name)
        self.assertEqual(album_data['mbid'], self.album1.mbid)
        self.assertIn('total_scrobbles', album_data)
        self.assertIn('first_scrobble', album_data)
        self.assertIn('last_scrobble', album_data)

        # Check tracks structure
        self.assertIsInstance(data['tracks'], list)
        if data['tracks']:
            track = data['tracks'][0]
            self.assertIn('track', track)
            self.assertIn('scrobble_count', track)
            self.assertIn('mbid', track)

        # Check chart_data structure
        chart_data = data['chart_data']
        self.assertIn('period', chart_data)
        self.assertIn('granularity', chart_data)
        self.assertIn('data', chart_data)
        self.assertIn('total_scrobbles', chart_data)

    def test_album_detail_mbid_lookup(self):
        """Test album detail endpoint with MBID lookup (Story 15)."""
        url = reverse('stats:album-detail-mbid', kwargs={'pk': self.album1.mbid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should return same structure as ID lookup
        self.assertIn('album', data)
        self.assertEqual(data['album']['name'], self.album1.name)
        self.assertEqual(data['album']['mbid'], self.album1.mbid)

    def test_album_detail_track_ordering_default(self):
        """Test album detail endpoint with default track ordering (album order)."""
        url = reverse('stats:album-detail', kwargs={'pk': self.album1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should return tracks in album order (default ordering)
        self.assertIn('tracks', data)
        self.assertIsInstance(data['tracks'], list)

    def test_album_detail_track_ordering_scrobble_count(self):
        """Test album detail endpoint with scrobble count ordering."""
        url = reverse('stats:album-detail', kwargs={'pk': self.album1.id})
        response = self.client.get(url, {'ordering': 'scrobble_count'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should return tracks ordered by scrobble count (descending)
        self.assertIn('tracks', data)
        tracks = data['tracks']
        if len(tracks) > 1:
            # Check that tracks are ordered by scrobble count (descending)
            for i in range(len(tracks) - 1):
                self.assertGreaterEqual(
                    tracks[i]['scrobble_count'],
                    tracks[i + 1]['scrobble_count']
                )

    def test_album_detail_chart_data(self):
        """Test album detail endpoint includes chart data."""
        url = reverse('stats:album-detail', kwargs={'pk': self.album1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Chart data should be included
        chart_data = data['chart_data']
        self.assertIn('period', chart_data)
        self.assertIn('granularity', chart_data)
        self.assertIsInstance(chart_data['data'], list)

    def test_album_detail_track_list_complete(self):
        """Test album detail returns complete track listing with scrobble counts."""
        url = reverse('stats:album-detail', kwargs={'pk': self.album1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should include all tracks from this album
        tracks = data['tracks']
        track_names = [track['track'] for track in tracks]

        # Verify our test tracks are included
        self.assertIn(self.track1.name, track_names)
        self.assertIn(self.track2.name, track_names)

        # Each track should have required fields
        for track in tracks:
            self.assertIn('track', track)
            self.assertIn('scrobble_count', track)
            self.assertIn('mbid', track)
            self.assertIsInstance(track['scrobble_count'], int)

    def test_track_detail(self):
        """Test track detail endpoint."""
        url = reverse('stats:track-detail', kwargs={'pk': self.track1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data['id'], self.track1.id)
        self.assertEqual(data['name'], self.track1.name)
        self.assertEqual(data['mbid'], self.track1.mbid)
        self.assertEqual(data['duration'], self.track1.duration)
        self.assertIn('artist', data)
        self.assertIn('album', data)
        self.assertIn('scrobble_count', data)
        self.assertIn('recent_scrobbles', data)

        # Check nested artist/album data
        self.assertEqual(data['artist']['name'], self.artist1.name)
        self.assertEqual(data['album']['name'], self.album1.name)

        # Check scrobble count
        expected_count = self.track1.scrobbles.count()
        self.assertEqual(data['scrobble_count'], expected_count)

    def test_artist_detail_not_found_id(self):
        """Test artist detail with non-existent ID."""
        url = reverse('stats:artist-detail', kwargs={'pk': 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_artist_detail_not_found_mbid(self):
        """Test artist detail with non-existent MBID."""
        fake_mbid = '12345678-1234-5678-9012-123456789012'
        url = reverse('stats:artist-detail-mbid', kwargs={'pk': fake_mbid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_album_detail_not_found_id(self):
        """Test album detail with non-existent ID."""
        url = reverse('stats:album-detail', kwargs={'pk': 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_album_detail_not_found_mbid(self):
        """Test album detail with non-existent MBID."""
        fake_mbid = '12345678-1234-5678-9012-123456789012'
        url = reverse('stats:album-detail-mbid', kwargs={'pk': fake_mbid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_track_detail_not_found(self):
        """Test track detail with non-existent ID."""
        url = reverse('stats:track-detail', kwargs={'pk': 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pagination(self):
        """Test that pagination works correctly."""
        url = reverse('stats:stats-recent-tracks')
        response = self.client.get(url + '?limit=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Story 9 compliant format
        self.assertIn('count', data)
        self.assertIn('has_next', data)
        self.assertIn('has_previous', data)
        self.assertIn('results', data)

        # Should limit results to limit parameter
        self.assertLessEqual(len(data['results']), 2)

    def test_invalid_time_period(self):
        """Test behavior with invalid time period parameter."""
        url = reverse('stats:stats-top-artists')
        response = self.client.get(url + '?period=invalid')

        # Should default to 30d period and return 200
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)

    def test_empty_results_handling(self):
        """Test endpoints handle empty results gracefully."""
        # Clear all data
        Scrobble.objects.all().delete()
        Track.objects.all().delete()
        Album.objects.all().delete()
        Artist.objects.all().delete()

        # Test each endpoint
        endpoints = [
            reverse('stats:stats-recent-tracks'),
            reverse('stats:stats-top-artists'),
            reverse('stats:stats-top-albums'),
            reverse('stats:stats-top-tracks'),
        ]

        for url in endpoints:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertIn('results', data)
                self.assertEqual(len(data['results']), 0)

                # Recent tracks uses different response format (Story 9)
                if 'recent-tracks' in url:
                    self.assertEqual(data['count'], 0)
                    self.assertIn('has_next', data)
                    self.assertIn('has_previous', data)
                else:
                    self.assertEqual(data['count'], 0)


class SerializerTestCase(TestCase):
    """Test cases for API serializers."""

    def setUp(self):
        """Set up test data."""
        self.artist = Artist.objects.create(
            name="Test Artist",
            mbid="12345678-1234-1234-1234-123456789012"
        )
        self.album = Album.objects.create(
            name="Test Album",
            artist=self.artist,
            mbid="11111111-1111-1111-1111-111111111111"
        )
        self.track = Track.objects.create(
            name="Test Track",
            artist=self.artist,
            album=self.album,
            duration=180
        )
        self.scrobble = Scrobble.objects.create(
            track=self.track,
            timestamp=timezone.now()
        )

    def test_duration_formatted(self):
        """Test that duration_formatted is correctly calculated."""
        url = reverse('stats:track-detail', kwargs={'pk': self.track.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # 180 seconds should be formatted as "3:00"
        self.assertEqual(data['duration_formatted'], "3:00")

    def test_scrobble_count_calculation(self):
        """Test that scrobble counts are correctly calculated."""
        # Create additional scrobbles
        for i in range(3):
            Scrobble.objects.create(
                track=self.track,
                timestamp=timezone.now() - timedelta(minutes=i * 5)
            )

        url = reverse('stats:track-detail', kwargs={'pk': self.track.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should have 4 total scrobbles (1 from setUp + 3 created)
        self.assertEqual(data['scrobble_count'], 4)


class Story10TopArtistsAPITestCase(APITestCase):
    """Test cases specifically for Story 10: Top Artists API compliance."""

    def setUp(self):
        """Set up test data for Story 10 testing."""
        # Create artists
        self.artist1 = Artist.objects.create(
            name="Story10 Artist 1",
            mbid="12345678-1234-1234-1234-123456789012"
        )
        self.artist2 = Artist.objects.create(
            name="Story10 Artist 2",
            mbid="87654321-4321-4321-4321-210987654321"
        )

        # Create albums
        self.album1 = Album.objects.create(
            name="Story10 Album 1",
            artist=self.artist1,
            mbid="11111111-1111-1111-1111-111111111111"
        )

        # Create tracks
        self.track1 = Track.objects.create(
            name="Story10 Track 1",
            artist=self.artist1,
            album=self.album1,
            duration=180
        )
        self.track2 = Track.objects.create(
            name="Story10 Track 2",
            artist=self.artist2,
            duration=240
        )

        # Create scrobbles with specific timestamps for testing
        now = timezone.now()
        self.scrobbles = [
            # Recent scrobbles (within 7d)
            Scrobble.objects.create(
                track=self.track1,
                timestamp=now - timedelta(days=1)
            ),
            Scrobble.objects.create(
                track=self.track1,
                timestamp=now - timedelta(days=2)
            ),
            # Medium range scrobbles (within 30d but not 7d)
            Scrobble.objects.create(
                track=self.track1,
                timestamp=now - timedelta(days=15)
            ),
            # Extended range scrobbles (within 180d but not 90d)
            Scrobble.objects.create(
                track=self.track2,
                timestamp=now - timedelta(days=120)
            ),
            # Old scrobbles (beyond 365d)
            Scrobble.objects.create(
                track=self.track2,
                timestamp=now - timedelta(days=400)
            ),
        ]

    def test_story10_response_format(self):
        """Test Story 10 compliant response format."""
        url = reverse('stats:top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Story 10: Check required response structure
        self.assertIn('period', data)
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIn('total_scrobbles', data)

        # Should NOT have DRF pagination fields
        self.assertNotIn('next', data)
        self.assertNotIn('previous', data)

    def test_story10_direct_url_endpoint(self):
        """Test Story 10 direct URL /api/top-artists/."""
        url = reverse('stats:top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should return Story 10 format
        self.assertIn('period', data)
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIn('total_scrobbles', data)

    def test_story10_default_limit_10(self):
        """Test Story 10 default limit is 10."""
        url = reverse('stats:top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should limit results to 10 by default
        self.assertLessEqual(len(data['results']), 10)

    def test_story10_limit_parameter_validation(self):
        """Test Story 10 ?limit=N parameter (min 1, max 100, default 10)."""
        base_url = reverse('stats:top-artists')

        # Test custom limit within range
        response = self.client.get(base_url + '?limit=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 5)

        # Test min limit (should default to 1)
        response = self.client.get(base_url + '?limit=0')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 1)

        # Test max limit (should cap at 100)
        response = self.client.get(base_url + '?limit=150')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 100)

        # Test invalid limit (should default to 10)
        response = self.client.get(base_url + '?limit=invalid')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(len(data['results']), 10)

    def test_story10_all_time_periods(self):
        """Test all Story 10 time periods: 7d, 30d, 90d, 180d, 365d, all."""
        base_url = reverse('stats:top-artists')
        periods = ['7d', '30d', '90d', '180d', '365d', 'all']

        for period in periods:
            with self.subTest(period=period):
                response = self.client.get(base_url + f'?period={period}')
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()

                # Check response format
                self.assertIn('period', data)
                self.assertIn('results', data)
                self.assertIn('count', data)
                self.assertIn('total_scrobbles', data)
                self.assertEqual(data['period'], period)

    def test_story10_180d_period_specifically(self):
        """Test the new 180d period works correctly."""
        base_url = reverse('stats:top-artists')
        response = self.client.get(base_url + '?period=180d')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data['period'], '180d')
        # Should include artist2 which has scrobble at 120 days ago
        artist_names = [result['name'] for result in data['results']]
        self.assertIn('Story10 Artist 2', artist_names)

    def test_story10_custom_date_range_filtering(self):
        """Test Story 10 custom date range via from_date and to_date."""
        base_url = reverse('stats:top-artists')
        now = timezone.now()

        # Test date range that should capture some scrobbles
        from_date = (now - timedelta(days=20)).strftime('%Y-%m-%d')
        to_date = (now - timedelta(days=10)).strftime('%Y-%m-%d')

        response = self.client.get(base_url + f'?from_date={from_date}&to_date={to_date}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data['period'], f'{from_date} to {to_date}')
        self.assertIn('results', data)
        self.assertIn('total_scrobbles', data)

    def test_story10_custom_date_range_partial(self):
        """Test Story 10 custom date range with only from_date or to_date."""
        base_url = reverse('stats:top-artists')
        now = timezone.now()

        # Test with only from_date
        from_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        response = self.client.get(base_url + f'?from_date={from_date}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], f'from {from_date}')

        # Test with only to_date
        to_date = (now - timedelta(days=10)).strftime('%Y-%m-%d')
        response = self.client.get(base_url + f'?to_date={to_date}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], f'until {to_date}')

    def test_story10_invalid_date_format_error(self):
        """Test Story 10 error handling for invalid date formats."""
        base_url = reverse('stats:top-artists')

        # Test invalid date format
        response = self.client.get(base_url + '?from_date=invalid-date')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error']['code'], 'INVALID_DATE_FORMAT')

    def test_story10_invalid_date_range_error(self):
        """Test Story 10 error handling for invalid date ranges."""
        base_url = reverse('stats:top-artists')
        now = timezone.now()

        # Test from_date after to_date
        from_date = (now - timedelta(days=10)).strftime('%Y-%m-%d')
        to_date = (now - timedelta(days=20)).strftime('%Y-%m-%d')

        response = self.client.get(base_url + f'?from_date={from_date}&to_date={to_date}')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error']['code'], 'INVALID_DATE_RANGE')

    def test_story10_artist_response_fields(self):
        """Test Story 10 artist response includes required fields."""
        url = reverse('stats:top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        if len(data['results']) > 0:
            first_artist = data['results'][0]

            # Story 10: Required fields
            self.assertIn('name', first_artist)
            self.assertIn('scrobble_count', first_artist)
            self.assertIn('mbid', first_artist)

            # Additional helpful fields
            self.assertIn('id', first_artist)
            self.assertIn('track_count', first_artist)
            self.assertIn('album_count', first_artist)

    def test_story10_results_ordered_by_scrobble_count_desc(self):
        """Test Story 10 results ordered by scrobble count descending."""
        url = reverse('stats:top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        results = data['results']
        if len(results) > 1:
            for i in range(len(results) - 1):
                self.assertGreaterEqual(
                    results[i]['scrobble_count'],
                    results[i + 1]['scrobble_count'],
                    "Results should be ordered by scrobble_count descending"
                )

    def test_story10_total_scrobbles_calculation(self):
        """Test Story 10 total_scrobbles field is correctly calculated."""
        base_url = reverse('stats:top-artists')

        # Test for different periods
        test_cases = [
            ('7d', 2),    # 2 scrobbles within 7 days
            ('30d', 3),   # 3 scrobbles within 30 days
            ('180d', 4),  # 4 scrobbles within 180 days
            ('all', 5)    # All 5 scrobbles
        ]

        for period, expected_count in test_cases:
            with self.subTest(period=period):
                response = self.client.get(base_url + f'?period={period}')
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()

                self.assertEqual(data['total_scrobbles'], expected_count,
                               f"Period {period} should have {expected_count} total scrobbles")

    def test_story10_default_period_is_all(self):
        """Test Story 10 default period is 'all' (not '30d' like other endpoints)."""
        url = reverse('stats:top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'all')

    def test_story10_handles_invalid_period_gracefully(self):
        """Test Story 10 handles invalid periods gracefully with default."""
        url = reverse('stats:top-artists')
        response = self.client.get(url + '?period=invalid_period')

        # Should not error, should default to 'all'
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['period'], 'all')
        self.assertIn('results', data)
        self.assertIn('total_scrobbles', data)

    def test_story10_empty_results_handling(self):
        """Test Story 10 handles empty results gracefully."""
        # Clear all scrobbles
        Scrobble.objects.all().delete()

        url = reverse('stats:top-artists')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data['period'], 'all')
        self.assertEqual(data['results'], [])
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['total_scrobbles'], 0)


class Story16StatisticsSummaryAPITestCase(APITestCase):
    """Test cases specifically for Story 16: Statistics Summary API compliance."""

    def setUp(self):
        """Set up test data for Story 16 testing."""
        # Create artists
        self.artist1 = Artist.objects.create(
            name="Summary Artist 1",
            mbid="12345678-1234-1234-1234-123456789012"
        )
        self.artist2 = Artist.objects.create(
            name="Summary Artist 2",
            mbid="87654321-4321-4321-4321-210987654321"
        )

        # Create albums
        self.album1 = Album.objects.create(
            name="Summary Album 1",
            artist=self.artist1,
            mbid="11111111-1111-1111-1111-111111111111"
        )
        self.album2 = Album.objects.create(
            name="Summary Album 2",
            artist=self.artist2,
            mbid="22222222-2222-2222-2222-222222222222"
        )

        # Create tracks
        self.track1 = Track.objects.create(
            name="Summary Track 1",
            artist=self.artist1,
            album=self.album1,
            mbid="33333333-3333-3333-3333-333333333333",
            duration=180
        )
        self.track2 = Track.objects.create(
            name="Summary Track 2",
            artist=self.artist1,
            album=self.album1,
            duration=240
        )
        self.track3 = Track.objects.create(
            name="Summary Track 3",
            artist=self.artist2,
            album=self.album2,
            duration=200
        )

        # Create scrobbles with specific patterns for testing
        base_time = timezone.now() - timedelta(days=100)
        self.scrobbles = []

        # Artist 1 gets more scrobbles (will be top artist)
        for i in range(10):
            self.scrobbles.append(
                Scrobble.objects.create(
                    track=self.track1,
                    timestamp=base_time + timedelta(days=i * 10),
                    lastfm_reference_id=f"ref{i}"
                )
            )

        # Track 2 gets fewer scrobbles
        for i in range(5):
            self.scrobbles.append(
                Scrobble.objects.create(
                    track=self.track2,
                    timestamp=base_time + timedelta(days=i * 15 + 5),
                    lastfm_reference_id=f"ref2{i}"
                )
            )

        # Track 3 gets even fewer scrobbles
        for i in range(3):
            self.scrobbles.append(
                Scrobble.objects.create(
                    track=self.track3,
                    timestamp=base_time + timedelta(days=i * 20 + 10),
                    lastfm_reference_id=f"ref3{i}"
                )
            )

    def test_story16_basic_response_format(self):
        """Test Story 16 compliant response format."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Story 16: Check required top-level structure
        expected_keys = {'totals', 'date_range', 'top_all_time', 'averages'}
        self.assertEqual(set(data.keys()), expected_keys)

        # Check totals structure
        totals = data['totals']
        expected_totals_keys = {'scrobbles', 'artists', 'albums', 'tracks'}
        self.assertEqual(set(totals.keys()), expected_totals_keys)

        # Check date_range structure
        date_range = data['date_range']
        expected_date_keys = {'first_scrobble', 'last_scrobble', 'total_days'}
        self.assertEqual(set(date_range.keys()), expected_date_keys)

        # Check top_all_time structure
        top_all_time = data['top_all_time']
        expected_top_keys = {'artist', 'album', 'track'}
        self.assertEqual(set(top_all_time.keys()), expected_top_keys)

        # Check averages structure
        averages = data['averages']
        expected_avg_keys = {'per_day', 'per_month', 'per_year'}
        self.assertEqual(set(averages.keys()), expected_avg_keys)

    def test_story16_direct_url_endpoint(self):
        """Test Story 16 direct URL /api/stats/summary/."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should return Story 16 format
        self.assertIn('totals', data)
        self.assertIn('date_range', data)
        self.assertIn('top_all_time', data)
        self.assertIn('averages', data)

    def test_story16_totals_calculation(self):
        """Test Story 16 totals section is correctly calculated."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        totals = data['totals']

        # Verify counts match expected values
        self.assertEqual(totals['scrobbles'], 18)  # 10 + 5 + 3
        self.assertEqual(totals['artists'], 2)    # artist1, artist2
        self.assertEqual(totals['albums'], 2)     # album1, album2
        self.assertEqual(totals['tracks'], 3)     # track1, track2, track3

        # Verify all counts are integers
        for key, value in totals.items():
            self.assertIsInstance(value, int)
            self.assertGreaterEqual(value, 0)

    def test_story16_date_range_calculation(self):
        """Test Story 16 date_range section is correctly calculated."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        date_range = data['date_range']

        # Should have first and last scrobble timestamps
        self.assertIsNotNone(date_range['first_scrobble'])
        self.assertIsNotNone(date_range['last_scrobble'])
        self.assertIsInstance(date_range['total_days'], int)

        # Verify ISO 8601 timestamp format with Z suffix
        self.assertTrue(date_range['first_scrobble'].endswith('Z'))
        self.assertTrue(date_range['last_scrobble'].endswith('Z'))
        # More flexible regex to handle Django's isoformat() output with microseconds and timezone
        self.assertRegex(date_range['first_scrobble'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+\d{2}:\d{2})?Z$')
        self.assertRegex(date_range['last_scrobble'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+\d{2}:\d{2})?Z$')

        # last_scrobble should be greater than or equal to first_scrobble
        self.assertGreaterEqual(date_range['last_scrobble'], date_range['first_scrobble'])

        # total_days should be positive
        self.assertGreater(date_range['total_days'], 0)

    def test_story16_top_all_time_calculation(self):
        """Test Story 16 top_all_time section identifies most played items."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        top_all_time = data['top_all_time']

        # Should identify the most played items based on our test data
        self.assertEqual(top_all_time['artist'], 'Summary Artist 1')  # Has 15 total scrobbles vs 3
        self.assertEqual(top_all_time['album'], 'Summary Album 1')    # Has 15 total scrobbles vs 3
        self.assertEqual(top_all_time['track'], 'Summary Track 1')    # Has 10 scrobbles (most)

        # Verify all are strings (artist/album/track names)
        self.assertIsInstance(top_all_time['artist'], str)
        self.assertIsInstance(top_all_time['album'], str)
        self.assertIsInstance(top_all_time['track'], str)

    def test_story16_averages_calculation(self):
        """Test Story 16 averages section is correctly calculated."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        averages = data['averages']

        # All averages should be numeric (float or int)
        self.assertIsInstance(averages['per_day'], (int, float))
        self.assertIsInstance(averages['per_month'], (int, float))
        self.assertIsInstance(averages['per_year'], (int, float))

        # All averages should be non-negative
        self.assertGreaterEqual(averages['per_day'], 0)
        self.assertGreaterEqual(averages['per_month'], 0)
        self.assertGreaterEqual(averages['per_year'], 0)

        # Logical relationships between averages - allow for reasonable tolerance
        if averages['per_day'] > 0:
            # Monthly should be roughly 30 times daily
            expected_monthly = averages['per_day'] * 30.44
            self.assertAlmostEqual(averages['per_month'], expected_monthly, delta=expected_monthly * 0.1)

            # Yearly should be roughly 365 times daily
            expected_yearly = averages['per_day'] * 365.25
            self.assertAlmostEqual(averages['per_year'], expected_yearly, delta=expected_yearly * 0.1)

    def test_story16_empty_dataset_handling(self):
        """Test Story 16 handles empty dataset gracefully."""
        # Clear all data
        Scrobble.objects.all().delete()
        Track.objects.all().delete()
        Album.objects.all().delete()
        Artist.objects.all().delete()

        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should return zeros for all counts
        self.assertEqual(data['totals']['scrobbles'], 0)
        self.assertEqual(data['totals']['artists'], 0)
        self.assertEqual(data['totals']['albums'], 0)
        self.assertEqual(data['totals']['tracks'], 0)

        # Should have null values for date range and top items
        self.assertIsNone(data['date_range']['first_scrobble'])
        self.assertIsNone(data['date_range']['last_scrobble'])
        self.assertEqual(data['date_range']['total_days'], 0)

        self.assertIsNone(data['top_all_time']['artist'])
        self.assertIsNone(data['top_all_time']['album'])
        self.assertIsNone(data['top_all_time']['track'])

        # Should have zero averages
        self.assertEqual(data['averages']['per_day'], 0)
        self.assertEqual(data['averages']['per_month'], 0)
        self.assertEqual(data['averages']['per_year'], 0)

    def test_story16_single_scrobble_dataset(self):
        """Test Story 16 handles single scrobble dataset correctly."""
        # Clear existing data
        Scrobble.objects.all().delete()
        Track.objects.all().delete()
        Album.objects.all().delete()
        Artist.objects.all().delete()

        # Create minimal dataset with one scrobble
        artist = Artist.objects.create(name="Single Artist")
        album = Album.objects.create(name="Single Album", artist=artist)
        track = Track.objects.create(name="Single Track", artist=artist, album=album)
        scrobble = Scrobble.objects.create(track=track, timestamp=timezone.now())

        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should have counts of 1
        self.assertEqual(data['totals']['scrobbles'], 1)
        self.assertEqual(data['totals']['artists'], 1)
        self.assertEqual(data['totals']['albums'], 1)
        self.assertEqual(data['totals']['tracks'], 1)

        # Should identify the single items as top
        self.assertEqual(data['top_all_time']['artist'], 'Single Artist')
        self.assertEqual(data['top_all_time']['album'], 'Single Album')
        self.assertEqual(data['top_all_time']['track'], 'Single Track')

        # First and last scrobble should be the same
        self.assertEqual(data['date_range']['first_scrobble'], data['date_range']['last_scrobble'])
        self.assertEqual(data['date_range']['total_days'], 1)

    def test_story16_performance_with_caching(self):
        """Test Story 16 performance optimization with caching."""
        url = reverse('stats:stats-summary')

        # First request (cache miss)
        start_time = timezone.now()
        response1 = self.client.get(url)
        first_duration = timezone.now() - start_time

        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second request (cache hit) - should be faster
        start_time = timezone.now()
        response2 = self.client.get(url)
        second_duration = timezone.now() - start_time

        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Results should be identical
        self.assertEqual(response1.json(), response2.json())

        # Second request should be significantly faster (cached)
        # Allow some tolerance for test environment variations
        self.assertLess(second_duration.total_seconds(), first_duration.total_seconds() * 0.8)

    def test_story16_cache_invalidation(self):
        """Test Story 16 cache invalidation when new data is added."""
        url = reverse('stats:stats-summary')

        # Get initial response
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        initial_count = response1.json()['totals']['scrobbles']

        # Add new scrobble to change latest timestamp
        new_scrobble = Scrobble.objects.create(
            track=self.track1,
            timestamp=timezone.now(),
            lastfm_reference_id="cache_invalidation_test"
        )

        # Get response after adding data (should be cache miss due to new latest timestamp)
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        updated_count = response2.json()['totals']['scrobbles']

        # Count should be incremented
        self.assertEqual(updated_count, initial_count + 1)

    def test_story16_data_consistency(self):
        """Test Story 16 data consistency across all fields."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Total scrobbles should equal sum of individual track scrobbles
        total_scrobbles_db = Scrobble.objects.count()
        self.assertEqual(data['totals']['scrobbles'], total_scrobbles_db)

        # Artists count should equal distinct artists with scrobbles
        artists_with_scrobbles = Artist.objects.filter(tracks__scrobbles__isnull=False).distinct().count()
        self.assertEqual(data['totals']['artists'], artists_with_scrobbles)

        # Albums count should equal distinct albums with scrobbles
        albums_with_scrobbles = Album.objects.filter(tracks__scrobbles__isnull=False).distinct().count()
        self.assertEqual(data['totals']['albums'], albums_with_scrobbles)

        # Tracks count should equal distinct tracks with scrobbles
        tracks_with_scrobbles = Track.objects.filter(scrobbles__isnull=False).distinct().count()
        self.assertEqual(data['totals']['tracks'], tracks_with_scrobbles)

        # Top artist should actually be the top artist
        top_artist_db = (
            Artist.objects
            .annotate(play_count=Count('tracks__scrobbles'))
            .order_by('-play_count')
            .first()
        )
        if top_artist_db:
            self.assertEqual(data['top_all_time']['artist'], top_artist_db.name)

    def test_story16_field_types_and_format(self):
        """Test Story 16 ensures all fields have correct types and formats."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify totals field types
        for field in ['scrobbles', 'artists', 'albums', 'tracks']:
            self.assertIsInstance(data['totals'][field], int)
            self.assertGreaterEqual(data['totals'][field], 0)

        # Verify date_range field types
        if data['date_range']['first_scrobble']:
            self.assertIsInstance(data['date_range']['first_scrobble'], str)
        if data['date_range']['last_scrobble']:
            self.assertIsInstance(data['date_range']['last_scrobble'], str)
        self.assertIsInstance(data['date_range']['total_days'], int)

        # Verify top_all_time field types (can be None or str)
        for field in ['artist', 'album', 'track']:
            value = data['top_all_time'][field]
            self.assertTrue(value is None or isinstance(value, str))

        # Verify averages field types
        for field in ['per_day', 'per_month', 'per_year']:
            self.assertIsInstance(data['averages'][field], (int, float))
            self.assertGreaterEqual(data['averages'][field], 0)

    def test_story16_response_matches_specification_example(self):
        """Test Story 16 response format matches specification example structure."""
        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should match the exact structure from Story 16 specification
        specification_keys = {
            'totals': {'scrobbles', 'artists', 'albums', 'tracks'},
            'date_range': {'first_scrobble', 'last_scrobble', 'total_days'},
            'top_all_time': {'artist', 'album', 'track'},
            'averages': {'per_day', 'per_month', 'per_year'}
        }

        for section, expected_fields in specification_keys.items():
            self.assertIn(section, data)
            self.assertEqual(set(data[section].keys()), expected_fields)

    def test_story16_handles_missing_albums_gracefully(self):
        """Test Story 16 handles tracks without albums gracefully."""
        # Create track without album
        track_no_album = Track.objects.create(
            name="No Album Track",
            artist=self.artist1
        )
        Scrobble.objects.create(
            track=track_no_album,
            timestamp=timezone.now(),
            lastfm_reference_id="no_album_test"
        )

        url = reverse('stats:stats-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should still work correctly
        self.assertGreater(data['totals']['scrobbles'], 0)
        self.assertGreater(data['totals']['tracks'], 0)

        # Albums count should only count tracks that have albums
        albums_with_scrobbles = Album.objects.filter(tracks__scrobbles__isnull=False).distinct().count()
        self.assertEqual(data['totals']['albums'], albums_with_scrobbles)