"""
Management command to calculate comprehensive statistics from scrobble data.

This command analyzes imported scrobble data and provides insights into:
- Basic counts (total scrobbles, unique tracks/artists/albums)
- Most played items (top artists, albums, tracks)
- Time-based analysis (date ranges, yearly/monthly breakdowns)
- Data quality metrics (MBID coverage, missing data)

Usage:
    python manage.py calculate_stats
    python manage.py calculate_stats --output-format=json --output-file=stats.json
    python manage.py calculate_stats --category=counts
    python manage.py calculate_stats --from-date=2020-01-01 --to-date=2024-12-31
"""

import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Sum, Avg, Max, Min, Q
from django.db.models.functions import Extract, TruncYear, TruncMonth, TruncDate
from django.utils import timezone

from music.models import Artist, Album, Track, Scrobble


class Command(BaseCommand):
    help = 'Calculate comprehensive statistics from scrobble data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-format',
            choices=['console', 'json'],
            default='console',
            help='Output format (default: console)'
        )

        parser.add_argument(
            '--output-file',
            help='Output file path for JSON format'
        )

        parser.add_argument(
            '--category',
            choices=['all', 'counts', 'top-items', 'time-analysis', 'data-quality'],
            default='all',
            help='Category of statistics to calculate (default: all)'
        )

        parser.add_argument(
            '--from-date',
            help='Start date for analysis (YYYY-MM-DD format)'
        )

        parser.add_argument(
            '--to-date',
            help='End date for analysis (YYYY-MM-DD format)'
        )

        parser.add_argument(
            '--top-n',
            type=int,
            default=10,
            help='Number of top items to show (default: 10)'
        )

    def handle(self, *args, **options):
        self.options = options
        self.verbosity = options.get('verbosity', 1)

        # Parse date filters
        date_filter = self._parse_date_filters()

        # Calculate statistics
        if self.verbosity >= 1:
            self.stdout.write("Calculating statistics...")

        stats = self._calculate_statistics(date_filter)

        # Output results
        if options['output_format'] == 'json':
            self._output_json(stats)
        else:
            self._output_console(stats)

    def _parse_date_filters(self):
        """Parse and validate date filter arguments."""
        date_filter = Q()

        if self.options.get('from_date'):
            try:
                from_date = datetime.strptime(self.options['from_date'], '%Y-%m-%d')
                from_date = timezone.make_aware(from_date)
                date_filter &= Q(timestamp__gte=from_date)
            except ValueError:
                raise CommandError("Invalid from-date format. Use YYYY-MM-DD.")

        if self.options.get('to_date'):
            try:
                to_date = datetime.strptime(self.options['to_date'], '%Y-%m-%d')
                # Include the entire end date
                to_date = timezone.make_aware(to_date) + timedelta(days=1)
                date_filter &= Q(timestamp__lt=to_date)
            except ValueError:
                raise CommandError("Invalid to-date format. Use YYYY-MM-DD.")

        return date_filter

    def _calculate_statistics(self, date_filter):
        """Calculate all statistics based on selected category."""
        stats = OrderedDict()
        category = self.options['category']

        if category in ['all', 'counts']:
            if self.verbosity >= 2:
                self.stdout.write("  Calculating basic counts...")
            stats['basic_counts'] = self._calculate_basic_counts(date_filter)

        if category in ['all', 'top-items']:
            if self.verbosity >= 2:
                self.stdout.write("  Calculating top items...")
            stats['top_items'] = self._calculate_top_items(date_filter)

        if category in ['all', 'time-analysis']:
            if self.verbosity >= 2:
                self.stdout.write("  Calculating time analysis...")
            stats['time_analysis'] = self._calculate_time_analysis(date_filter)

        if category in ['all', 'data-quality']:
            if self.verbosity >= 2:
                self.stdout.write("  Calculating data quality metrics...")
            stats['data_quality'] = self._calculate_data_quality(date_filter)

        return stats

    def _calculate_basic_counts(self, date_filter):
        """Calculate basic count statistics."""
        scrobble_qs = Scrobble.objects.filter(date_filter)

        # Basic counts
        total_scrobbles = scrobble_qs.count()

        if total_scrobbles == 0:
            return {
                'total_scrobbles': 0,
                'unique_tracks': 0,
                'unique_artists': 0,
                'unique_albums': 0,
                'avg_scrobbles_per_track': 0,
                'avg_scrobbles_per_artist': 0,
                'avg_scrobbles_per_album': 0,
            }

        unique_tracks = scrobble_qs.values('track').distinct().count()
        unique_artists = scrobble_qs.values('track__artist').distinct().count()
        # Count unique albums, excluding null albums
        unique_albums = scrobble_qs.exclude(track__album__isnull=True).values('track__album').distinct().count()

        return {
            'total_scrobbles': total_scrobbles,
            'unique_tracks': unique_tracks,
            'unique_artists': unique_artists,
            'unique_albums': unique_albums,
            'avg_scrobbles_per_track': round(total_scrobbles / unique_tracks, 1) if unique_tracks else 0,
            'avg_scrobbles_per_artist': round(total_scrobbles / unique_artists, 1) if unique_artists else 0,
            'avg_scrobbles_per_album': round(total_scrobbles / unique_albums, 1) if unique_albums else 0,
        }

    def _calculate_top_items(self, date_filter):
        """Calculate most played artists, albums, and tracks."""
        top_n = self.options['top_n']

        # Most played artists
        top_artists = (
            Artist.objects
            .annotate(play_count=Count('tracks__scrobbles', filter=date_filter))
            .filter(play_count__gt=0)
            .order_by('-play_count')[:top_n]
            .values('name', 'play_count', 'mbid')
        )

        # Most played albums
        top_albums = (
            Album.objects
            .annotate(play_count=Count('tracks__scrobbles', filter=date_filter))
            .filter(play_count__gt=0)
            .select_related('artist')
            .order_by('-play_count')[:top_n]
            .values('name', 'artist__name', 'play_count', 'mbid')
        )

        # Most played tracks
        top_tracks = (
            Track.objects
            .annotate(play_count=Count('scrobbles', filter=date_filter))
            .filter(play_count__gt=0)
            .select_related('artist', 'album')
            .order_by('-play_count')[:top_n]
            .values('name', 'artist__name', 'album__name', 'play_count', 'duration', 'mbid')
        )

        return {
            'top_artists': list(top_artists),
            'top_albums': list(top_albums),
            'top_tracks': list(top_tracks),
        }

    def _calculate_time_analysis(self, date_filter):
        """Calculate time-based statistics."""
        scrobble_qs = Scrobble.objects.filter(date_filter)

        if not scrobble_qs.exists():
            return {
                'date_range': {'first_scrobble': None, 'last_scrobble': None},
                'yearly_breakdown': {},
                'monthly_breakdown': {},
                'daily_patterns': {},
                'total_days_active': 0,
            }

        # Date range
        date_range = scrobble_qs.aggregate(
            first_scrobble=Min('timestamp'),
            last_scrobble=Max('timestamp')
        )

        # Yearly breakdown
        yearly_breakdown = (
            scrobble_qs
            .annotate(year=Extract('timestamp', 'year'))
            .values('year')
            .annotate(count=Count('id'))
            .order_by('year')
        )
        yearly_breakdown = {str(int(item['year'])): item['count'] for item in yearly_breakdown}

        # Monthly breakdown (last 12 months)
        monthly_breakdown = (
            scrobble_qs
            .annotate(
                year=Extract('timestamp', 'year'),
                month=Extract('timestamp', 'month')
            )
            .values('year', 'month')
            .annotate(count=Count('id'))
            .order_by('year', 'month')
        )
        monthly_breakdown = {
            f"{int(item['year'])}-{int(item['month']):02d}": item['count']
            for item in monthly_breakdown
        }

        # Daily patterns (day of week)
        daily_patterns = (
            scrobble_qs
            .annotate(weekday=Extract('timestamp', 'week_day'))
            .values('weekday')
            .annotate(count=Count('id'))
            .order_by('weekday')
        )

        # Convert weekday numbers to names
        weekday_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        daily_patterns = {
            weekday_names[item['weekday'] - 1]: item['count']
            for item in daily_patterns
        }

        # Total unique active days
        total_days_active = (
            scrobble_qs
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .distinct()
            .count()
        )

        return {
            'date_range': {
                'first_scrobble': date_range['first_scrobble'],
                'last_scrobble': date_range['last_scrobble']
            },
            'yearly_breakdown': yearly_breakdown,
            'monthly_breakdown': monthly_breakdown,
            'daily_patterns': daily_patterns,
            'total_days_active': total_days_active,
        }

    def _calculate_data_quality(self, date_filter):
        """Calculate data quality metrics."""
        # Get counts for entities that appear in filtered scrobbles
        scrobble_qs = Scrobble.objects.filter(date_filter)

        if not scrobble_qs.exists():
            return {
                'mbid_coverage': {'artists': 0, 'albums': 0, 'tracks': 0},
                'missing_data': {'albums_without_mbid': 0, 'tracks_without_album': 0},
                'data_completeness_score': 0,
            }

        # Get unique entities from filtered scrobbles
        unique_artist_ids = set(scrobble_qs.values_list('track__artist_id', flat=True).distinct())
        unique_album_ids = set(scrobble_qs.exclude(track__album__isnull=True).values_list('track__album_id', flat=True).distinct())
        unique_track_ids = set(scrobble_qs.values_list('track_id', flat=True).distinct())

        # MBID coverage
        artists_with_mbid = Artist.objects.filter(
            id__in=unique_artist_ids,
            mbid__isnull=False
        ).count()

        albums_with_mbid = Album.objects.filter(
            id__in=unique_album_ids,
            mbid__isnull=False
        ).count()

        tracks_with_mbid = Track.objects.filter(
            id__in=unique_track_ids,
            mbid__isnull=False
        ).count()

        total_artists = len(unique_artist_ids)
        total_albums = len(unique_album_ids)
        total_tracks = len(unique_track_ids)

        # Missing data analysis
        tracks_without_album = Track.objects.filter(
            id__in=unique_track_ids,
            album__isnull=True
        ).count()

        # Calculate completeness score
        total_entities = total_artists + total_albums + total_tracks
        entities_with_mbid = artists_with_mbid + albums_with_mbid + tracks_with_mbid
        completeness_score = round((entities_with_mbid / total_entities) * 100, 1) if total_entities else 0

        return {
            'mbid_coverage': {
                'artists': round((artists_with_mbid / total_artists) * 100, 1) if total_artists else 0,
                'albums': round((albums_with_mbid / total_albums) * 100, 1) if total_albums else 0,
                'tracks': round((tracks_with_mbid / total_tracks) * 100, 1) if total_tracks else 0,
            },
            'missing_data': {
                'tracks_without_album': tracks_without_album,
                'albums_without_mbid': total_albums - albums_with_mbid,
                'artists_without_mbid': total_artists - artists_with_mbid,
            },
            'data_completeness_score': completeness_score,
        }

    def _output_console(self, stats):
        """Output statistics to console in human-readable format."""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS("    SCROBBLARR STATISTICS"))
        self.stdout.write(self.style.SUCCESS("=" * 50))

        # Basic counts
        if 'basic_counts' in stats:
            self._output_basic_counts_console(stats['basic_counts'])

        # Top items
        if 'top_items' in stats:
            self._output_top_items_console(stats['top_items'])

        # Time analysis
        if 'time_analysis' in stats:
            self._output_time_analysis_console(stats['time_analysis'])

        # Data quality
        if 'data_quality' in stats:
            self._output_data_quality_console(stats['data_quality'])

    def _output_basic_counts_console(self, counts):
        """Output basic counts to console."""
        self.stdout.write(self.style.HTTP_INFO("\nBasic Counts:"))
        self.stdout.write(f"  Total Scrobbles: {counts['total_scrobbles']:,}")
        self.stdout.write(f"  Unique Tracks: {counts['unique_tracks']:,}")
        self.stdout.write(f"  Unique Artists: {counts['unique_artists']:,}")
        self.stdout.write(f"  Unique Albums: {counts['unique_albums']:,}")
        self.stdout.write(f"  Avg Scrobbles per Track: {counts['avg_scrobbles_per_track']}")
        self.stdout.write(f"  Avg Scrobbles per Artist: {counts['avg_scrobbles_per_artist']}")
        self.stdout.write(f"  Avg Scrobbles per Album: {counts['avg_scrobbles_per_album']}")

    def _output_top_items_console(self, top_items):
        """Output top items to console."""
        top_n = self.options['top_n']

        # Top Artists
        self.stdout.write(self.style.HTTP_INFO(f"\nTop {top_n} Artists:"))
        for i, artist in enumerate(top_items['top_artists'], 1):
            mbid_indicator = "✓" if artist['mbid'] else "✗"
            self.stdout.write(f"  {i:2d}. {artist['name']} ({artist['play_count']:,} plays) {mbid_indicator}")

        # Top Albums
        self.stdout.write(self.style.HTTP_INFO(f"\nTop {top_n} Albums:"))
        for i, album in enumerate(top_items['top_albums'], 1):
            mbid_indicator = "✓" if album['mbid'] else "✗"
            self.stdout.write(f"  {i:2d}. {album['name']} by {album['artist__name']} ({album['play_count']:,} plays) {mbid_indicator}")

        # Top Tracks
        self.stdout.write(self.style.HTTP_INFO(f"\nTop {top_n} Tracks:"))
        for i, track in enumerate(top_items['top_tracks'], 1):
            mbid_indicator = "✓" if track['mbid'] else "✗"
            duration_str = f" ({track['duration']//60}:{track['duration']%60:02d})" if track['duration'] else ""
            album_str = f" from {track['album__name']}" if track['album__name'] else ""
            self.stdout.write(f"  {i:2d}. {track['name']} by {track['artist__name']}{album_str}{duration_str} ({track['play_count']:,} plays) {mbid_indicator}")

    def _output_time_analysis_console(self, time_analysis):
        """Output time analysis to console."""
        self.stdout.write(self.style.HTTP_INFO("\nTime Analysis:"))

        date_range = time_analysis['date_range']
        if date_range['first_scrobble'] and date_range['last_scrobble']:
            first = date_range['first_scrobble'].strftime('%Y-%m-%d')
            last = date_range['last_scrobble'].strftime('%Y-%m-%d')
            self.stdout.write(f"  Date Range: {first} to {last}")

            # Calculate total period
            delta = date_range['last_scrobble'] - date_range['first_scrobble']
            self.stdout.write(f"  Total Period: {delta.days:,} days")
            self.stdout.write(f"  Active Days: {time_analysis['total_days_active']:,}")

        # Yearly breakdown
        if time_analysis['yearly_breakdown']:
            self.stdout.write("\n  Yearly Breakdown:")
            for year, count in time_analysis['yearly_breakdown'].items():
                self.stdout.write(f"    {year}: {count:,} scrobbles")

        # Most active periods
        if time_analysis['yearly_breakdown']:
            most_active_year = max(time_analysis['yearly_breakdown'].items(), key=lambda x: x[1])
            self.stdout.write(f"\n  Most Active Year: {most_active_year[0]} ({most_active_year[1]:,} scrobbles)")

        if time_analysis['daily_patterns']:
            most_active_day = max(time_analysis['daily_patterns'].items(), key=lambda x: x[1])
            self.stdout.write(f"  Most Active Day: {most_active_day[0]} ({most_active_day[1]:,} scrobbles)")

    def _output_data_quality_console(self, data_quality):
        """Output data quality metrics to console."""
        self.stdout.write(self.style.HTTP_INFO("\nData Quality:"))

        mbid_coverage = data_quality['mbid_coverage']
        self.stdout.write(f"  MBID Coverage:")
        self.stdout.write(f"    Artists: {mbid_coverage['artists']:.1f}%")
        self.stdout.write(f"    Albums: {mbid_coverage['albums']:.1f}%")
        self.stdout.write(f"    Tracks: {mbid_coverage['tracks']:.1f}%")

        missing_data = data_quality['missing_data']
        self.stdout.write(f"  Missing Data:")
        self.stdout.write(f"    Tracks without Album: {missing_data['tracks_without_album']:,}")
        self.stdout.write(f"    Albums without MBID: {missing_data['albums_without_mbid']:,}")
        self.stdout.write(f"    Artists without MBID: {missing_data['artists_without_mbid']:,}")

        score = data_quality['data_completeness_score']
        self.stdout.write(f"\n  Overall Data Completeness: {score:.1f}%")

    def _output_json(self, stats):
        """Output statistics as JSON."""
        # Convert datetime objects to ISO format strings for JSON serialization
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        output = {
            'generated_at': timezone.now().isoformat(),
            'filters': {
                'from_date': self.options.get('from_date'),
                'to_date': self.options.get('to_date'),
                'category': self.options['category'],
            },
            'statistics': stats
        }

        if self.options.get('output_file'):
            with open(self.options['output_file'], 'w') as f:
                json.dump(output, f, indent=2, default=serialize_datetime)
            self.stdout.write(
                self.style.SUCCESS(f"Statistics saved to {self.options['output_file']}")
            )
        else:
            json.dump(output, sys.stdout, indent=2, default=serialize_datetime)
            sys.stdout.write('\n')