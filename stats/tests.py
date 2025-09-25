from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
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

    def test_top_albums(self):
        """Test top albums endpoint."""
        url = reverse('stats:stats-top-albums')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)

        if len(data['results']) > 0:
            first_album = data['results'][0]
            self.assertIn('id', first_album)
            self.assertIn('name', first_album)
            self.assertIn('artist_name', first_album)
            self.assertIn('artist_id', first_album)
            self.assertIn('scrobble_count', first_album)
            self.assertIn('track_count', first_album)

    def test_top_tracks(self):
        """Test top tracks endpoint."""
        url = reverse('stats:stats-top-tracks')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)

        if len(data['results']) > 0:
            first_track = data['results'][0]
            self.assertIn('id', first_track)
            self.assertIn('name', first_track)
            self.assertIn('artist_name', first_track)
            self.assertIn('artist_id', first_track)
            self.assertIn('album_name', first_track)
            self.assertIn('album_id', first_track)
            self.assertIn('scrobble_count', first_track)
            self.assertIn('duration', first_track)

    def test_artist_detail(self):
        """Test artist detail endpoint."""
        url = reverse('stats:artist-detail', kwargs={'pk': self.artist1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data['id'], self.artist1.id)
        self.assertEqual(data['name'], self.artist1.name)
        self.assertEqual(data['mbid'], self.artist1.mbid)
        self.assertIn('albums', data)
        self.assertIn('top_tracks', data)
        self.assertIn('track_count', data)
        self.assertIn('album_count', data)
        self.assertIn('scrobble_count', data)

        # Check albums are included
        self.assertTrue(len(data['albums']) > 0)
        self.assertEqual(data['albums'][0]['name'], self.album1.name)

        # Check top tracks are included
        self.assertTrue(len(data['top_tracks']) > 0)

    def test_album_detail(self):
        """Test album detail endpoint."""
        url = reverse('stats:album-detail', kwargs={'pk': self.album1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data['id'], self.album1.id)
        self.assertEqual(data['name'], self.album1.name)
        self.assertEqual(data['mbid'], self.album1.mbid)
        self.assertIn('artist', data)
        self.assertIn('tracks', data)
        self.assertIn('track_count', data)
        self.assertIn('scrobble_count', data)

        # Check artist details are included
        self.assertEqual(data['artist']['name'], self.artist1.name)

        # Check tracks are included
        self.assertTrue(len(data['tracks']) > 0)
        track_names = [track['name'] for track in data['tracks']]
        self.assertIn(self.track1.name, track_names)
        self.assertIn(self.track2.name, track_names)

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

    def test_artist_detail_not_found(self):
        """Test artist detail with non-existent ID."""
        url = reverse('stats:artist-detail', kwargs={'pk': 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_album_detail_not_found(self):
        """Test album detail with non-existent ID."""
        url = reverse('stats:album-detail', kwargs={'pk': 99999})
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