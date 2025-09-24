import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.utils import timezone
from django.core.validators import URLValidator, ValidationError as DjangoValidationError
from django.db.models import Count, Q

from music.models import Artist, Album, Track, Scrobble, mbid_validator


class ValidationIssue:
    """Represents a single validation issue found during data validation."""

    def __init__(self, category: str, severity: str, message: str,
                 model_type: str = None, record_id: int = None,
                 record_details: dict = None, fix_available: bool = False):
        self.category = category
        self.severity = severity  # 'error', 'warning', 'info'
        self.message = message
        self.model_type = model_type
        self.record_id = record_id
        self.record_details = record_details or {}
        self.fix_available = fix_available

    def to_dict(self) -> dict:
        """Convert issue to dictionary for JSON export."""
        return {
            'category': self.category,
            'severity': self.severity,
            'message': self.message,
            'model_type': self.model_type,
            'record_id': self.record_id,
            'record_details': self.record_details,
            'fix_available': self.fix_available
        }


class Command(BaseCommand):
    help = 'Validate data integrity and quality of imported scrobble data'

    def __init__(self):
        super().__init__()
        self.issues = []
        self.fixes_applied = []
        self.stats = defaultdict(int)

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix common data quality issues automatically'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed validation information'
        )
        parser.add_argument(
            '--output-format',
            choices=['text', 'json'],
            default='text',
            help='Output format for validation results (default: text)'
        )
        parser.add_argument(
            '--category',
            choices=[
                'orphaned', 'duplicates', 'missing_data',
                'timestamps', 'data_consistency', 'all'
            ],
            default='all',
            help='Specific validation category to run (default: all)'
        )

    def handle(self, *args, **options):
        self.fix_mode = options['fix']
        self.verbose = options['verbose']
        self.output_format = options['output_format']
        self.category_filter = options['category']

        self.stdout.write(
            self.style.SUCCESS('Starting data validation...')
        )

        if self.fix_mode:
            self.stdout.write(
                self.style.WARNING('FIX MODE ENABLED - Changes will be made to your data')
            )

        # Run validation checks
        self._run_validation_checks()

        # Apply fixes if requested
        if self.fix_mode and self.issues:
            self._apply_fixes()

        # Generate report
        self._generate_report()

        # Summary
        self._print_summary()

    def _run_validation_checks(self):
        """Run all validation checks based on category filter."""
        if self.category_filter in ['orphaned', 'all']:
            self._check_orphaned_records()

        if self.category_filter in ['duplicates', 'all']:
            self._check_duplicates()

        if self.category_filter in ['missing_data', 'all']:
            self._check_missing_data()

        if self.category_filter in ['timestamps', 'all']:
            self._check_timestamps()

        if self.category_filter in ['data_consistency', 'all']:
            self._check_data_consistency()

    def _check_orphaned_records(self):
        """Check for orphaned records that violate referential integrity."""
        if self.verbose:
            self.stdout.write('Checking for orphaned records...')

        # Check for albums without valid artists (should not exist due to FK)
        orphaned_albums = Album.objects.filter(artist__isnull=True)
        for album in orphaned_albums:
            self._add_issue(
                'orphaned', 'error',
                f'Album "{album.name}" has no valid artist reference',
                'album', album.id,
                {'name': album.name, 'mbid': album.mbid}
            )

        # Check for tracks without valid artists
        orphaned_tracks_no_artist = Track.objects.filter(artist__isnull=True)
        for track in orphaned_tracks_no_artist:
            self._add_issue(
                'orphaned', 'error',
                f'Track "{track.name}" has no valid artist reference',
                'track', track.id,
                {'name': track.name, 'mbid': track.mbid},
                fix_available=False  # This would require manual intervention
            )

        # Check for tracks with invalid album references
        # (albums that don't match the track's artist)
        mismatched_tracks = Track.objects.filter(
            album__isnull=False
        ).exclude(
            album__artist=models.F('artist')
        )
        for track in mismatched_tracks:
            self._add_issue(
                'orphaned', 'error',
                f'Track "{track.name}" belongs to album "{track.album.name}" '
                f'but album is by "{track.album.artist.name}" while track is by "{track.artist.name}"',
                'track', track.id,
                {
                    'track_name': track.name,
                    'track_artist': track.artist.name,
                    'album_name': track.album.name,
                    'album_artist': track.album.artist.name
                },
                fix_available=True
            )

        # Check for scrobbles without valid tracks
        orphaned_scrobbles = Scrobble.objects.filter(track__isnull=True)
        for scrobble in orphaned_scrobbles:
            self._add_issue(
                'orphaned', 'error',
                f'Scrobble at {scrobble.timestamp} has no valid track reference',
                'scrobble', scrobble.id,
                {'timestamp': scrobble.timestamp.isoformat()}
            )

    def _check_duplicates(self):
        """Check for duplicate records."""
        if self.verbose:
            self.stdout.write('Checking for duplicates...')

        # Check for duplicate scrobbles (same track + timestamp)
        duplicate_scrobbles = (
            Scrobble.objects
            .values('track', 'timestamp')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )

        for duplicate in duplicate_scrobbles:
            scrobbles = Scrobble.objects.filter(
                track=duplicate['track'],
                timestamp=duplicate['timestamp']
            ).order_by('id')

            track = Track.objects.get(id=duplicate['track'])
            self._add_issue(
                'duplicates', 'warning',
                f'Found {duplicate["count"]} duplicate scrobbles for track "{track.name}" '
                f'at {duplicate["timestamp"]}',
                'scrobble', None,
                {
                    'track_name': track.name,
                    'artist_name': track.artist.name,
                    'timestamp': duplicate['timestamp'].isoformat(),
                    'duplicate_ids': list(scrobbles.values_list('id', flat=True)),
                    'count': duplicate['count']
                },
                fix_available=True
            )

        # Check for potential duplicate artists (same name, different MBID)
        artists_by_name = (
            Artist.objects
            .values('name')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )

        for artist_group in artists_by_name:
            artists = Artist.objects.filter(name=artist_group['name']).order_by('id')
            # Check if they have different MBIDs
            mbids = set(filter(None, artists.values_list('mbid', flat=True)))
            if len(mbids) > 1:
                self._add_issue(
                    'duplicates', 'warning',
                    f'Artist "{artist_group["name"]}" appears {artist_group["count"]} times '
                    f'with different MBIDs: {", ".join(mbids)}',
                    'artist', None,
                    {
                        'name': artist_group['name'],
                        'artist_ids': list(artists.values_list('id', flat=True)),
                        'mbids': list(mbids)
                    },
                    fix_available=False  # Requires manual review
                )

        # Check for potential duplicate albums (same name + artist, different MBID)
        albums_by_name_artist = (
            Album.objects
            .values('name', 'artist')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )

        for album_group in albums_by_name_artist:
            albums = Album.objects.filter(
                name=album_group['name'],
                artist=album_group['artist']
            ).order_by('id')
            mbids = set(filter(None, albums.values_list('mbid', flat=True)))
            if len(mbids) > 1:
                artist_name = Artist.objects.get(id=album_group['artist']).name
                self._add_issue(
                    'duplicates', 'warning',
                    f'Album "{album_group["name"]}" by "{artist_name}" appears '
                    f'{album_group["count"]} times with different MBIDs',
                    'album', None,
                    {
                        'name': album_group['name'],
                        'artist_name': artist_name,
                        'album_ids': list(albums.values_list('id', flat=True)),
                        'mbids': list(mbids)
                    },
                    fix_available=False  # Requires manual review
                )

    def _check_missing_data(self):
        """Check for records with missing critical data."""
        if self.verbose:
            self.stdout.write('Checking for missing data...')

        # Check for artists with empty names (should be prevented by constraints)
        empty_name_artists = Artist.objects.filter(
            Q(name__isnull=True) | Q(name='') | Q(name__regex=r'^\s*$')
        )
        for artist in empty_name_artists:
            self._add_issue(
                'missing_data', 'error',
                f'Artist (ID: {artist.id}) has empty or null name',
                'artist', artist.id,
                {'mbid': artist.mbid},
                fix_available=False
            )

        # Check for albums with empty names
        empty_name_albums = Album.objects.filter(
            Q(name__isnull=True) | Q(name='') | Q(name__regex=r'^\s*$')
        )
        for album in empty_name_albums:
            self._add_issue(
                'missing_data', 'error',
                f'Album (ID: {album.id}) by "{album.artist.name}" has empty or null name',
                'album', album.id,
                {'artist_name': album.artist.name, 'mbid': album.mbid},
                fix_available=False
            )

        # Check for tracks with empty names
        empty_name_tracks = Track.objects.filter(
            Q(name__isnull=True) | Q(name='') | Q(name__regex=r'^\s*$')
        )
        for track in empty_name_tracks:
            self._add_issue(
                'missing_data', 'error',
                f'Track (ID: {track.id}) by "{track.artist.name}" has empty or null name',
                'track', track.id,
                {
                    'artist_name': track.artist.name,
                    'album_name': track.album.name if track.album else None,
                    'mbid': track.mbid
                },
                fix_available=False
            )

        # Check for scrobbles without timestamps (should not happen)
        no_timestamp_scrobbles = Scrobble.objects.filter(timestamp__isnull=True)
        for scrobble in no_timestamp_scrobbles:
            self._add_issue(
                'missing_data', 'error',
                f'Scrobble (ID: {scrobble.id}) has no timestamp',
                'scrobble', scrobble.id,
                {'track_name': scrobble.track.name},
                fix_available=False
            )

    def _check_timestamps(self):
        """Check for invalid timestamps."""
        if self.verbose:
            self.stdout.write('Checking timestamps...')

        now = timezone.now()
        # Check for future timestamps
        future_scrobbles = Scrobble.objects.filter(timestamp__gt=now)
        for scrobble in future_scrobbles:
            self._add_issue(
                'timestamps', 'error',
                f'Scrobble has future timestamp: {scrobble.timestamp}',
                'scrobble', scrobble.id,
                {
                    'timestamp': scrobble.timestamp.isoformat(),
                    'track_name': scrobble.track.name,
                    'artist_name': scrobble.track.artist.name
                },
                fix_available=True
            )

        # Check for very old timestamps (before 1970)
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        old_scrobbles = Scrobble.objects.filter(timestamp__lt=epoch)
        for scrobble in old_scrobbles:
            self._add_issue(
                'timestamps', 'warning',
                f'Scrobble has very old timestamp: {scrobble.timestamp}',
                'scrobble', scrobble.id,
                {
                    'timestamp': scrobble.timestamp.isoformat(),
                    'track_name': scrobble.track.name,
                    'artist_name': scrobble.track.artist.name
                },
                fix_available=True
            )

        # Check for unreasonably old timestamps (before music streaming era)
        early_streaming = datetime(1995, 1, 1, tzinfo=timezone.utc)
        very_old_scrobbles = Scrobble.objects.filter(timestamp__lt=early_streaming)
        if very_old_scrobbles.count() > 0:
            self._add_issue(
                'timestamps', 'info',
                f'Found {very_old_scrobbles.count()} scrobbles before 1995 '
                f'(before digital music era)',
                'scrobble', None,
                {'count': very_old_scrobbles.count()},
                fix_available=False
            )

    def _check_data_consistency(self):
        """Check for data consistency issues."""
        if self.verbose:
            self.stdout.write('Checking data consistency...')

        # Check MBID format validity
        url_validator = URLValidator()

        # Check artist MBIDs
        artists_with_mbid = Artist.objects.exclude(mbid__isnull=True).exclude(mbid='')
        for artist in artists_with_mbid:
            try:
                mbid_validator(artist.mbid)
            except DjangoValidationError:
                self._add_issue(
                    'data_consistency', 'warning',
                    f'Artist "{artist.name}" has invalid MBID format: {artist.mbid}',
                    'artist', artist.id,
                    {'name': artist.name, 'mbid': artist.mbid},
                    fix_available=True
                )

        # Check album MBIDs
        albums_with_mbid = Album.objects.exclude(mbid__isnull=True).exclude(mbid='')
        for album in albums_with_mbid:
            try:
                mbid_validator(album.mbid)
            except DjangoValidationError:
                self._add_issue(
                    'data_consistency', 'warning',
                    f'Album "{album.name}" has invalid MBID format: {album.mbid}',
                    'album', album.id,
                    {
                        'name': album.name,
                        'artist_name': album.artist.name,
                        'mbid': album.mbid
                    },
                    fix_available=True
                )

        # Check track MBIDs
        tracks_with_mbid = Track.objects.exclude(mbid__isnull=True).exclude(mbid='')
        for track in tracks_with_mbid:
            try:
                mbid_validator(track.mbid)
            except DjangoValidationError:
                self._add_issue(
                    'data_consistency', 'warning',
                    f'Track "{track.name}" has invalid MBID format: {track.mbid}',
                    'track', track.id,
                    {
                        'name': track.name,
                        'artist_name': track.artist.name,
                        'mbid': track.mbid
                    },
                    fix_available=True
                )

        # Check URL validity
        for model_class, model_name in [(Artist, 'artist'), (Album, 'album'), (Track, 'track')]:
            records_with_url = model_class.objects.exclude(url__isnull=True).exclude(url='')
            for record in records_with_url:
                try:
                    url_validator(record.url)
                except DjangoValidationError:
                    self._add_issue(
                        'data_consistency', 'warning',
                        f'{model_name.title()} "{record.name}" has invalid URL: {record.url}',
                        model_name, record.id,
                        {'name': record.name, 'url': record.url},
                        fix_available=True
                    )

        # Check track duration validity
        invalid_duration_tracks = Track.objects.filter(
            Q(duration__lt=0) | Q(duration__gt=7200)  # Longer than 2 hours
        )
        for track in invalid_duration_tracks:
            self._add_issue(
                'data_consistency', 'warning',
                f'Track "{track.name}" has unusual duration: {track.duration} seconds',
                'track', track.id,
                {
                    'name': track.name,
                    'artist_name': track.artist.name,
                    'duration': track.duration
                },
                fix_available=True
            )

    def _apply_fixes(self):
        """Apply automatic fixes for issues that can be safely resolved."""
        if not self.issues:
            return

        fixable_issues = [issue for issue in self.issues if issue.fix_available]
        if not fixable_issues:
            self.stdout.write('No fixable issues found.')
            return

        self.stdout.write(
            f'Attempting to fix {len(fixable_issues)} issues...'
        )

        with transaction.atomic():
            for issue in fixable_issues:
                try:
                    if self._apply_single_fix(issue):
                        self.fixes_applied.append(issue)
                except Exception as e:
                    self.stderr.write(f'Failed to fix issue: {issue.message}. Error: {str(e)}')

        self.stdout.write(
            self.style.SUCCESS(f'Applied {len(self.fixes_applied)} fixes.')
        )

    def _apply_single_fix(self, issue: ValidationIssue) -> bool:
        """Apply a single fix for a validation issue."""
        if issue.category == 'duplicates' and issue.model_type == 'scrobble':
            # Remove duplicate scrobbles, keep the first one
            duplicate_ids = issue.record_details.get('duplicate_ids', [])
            if len(duplicate_ids) > 1:
                # Keep first, delete rest
                Scrobble.objects.filter(id__in=duplicate_ids[1:]).delete()
                return True

        elif issue.category == 'timestamps':
            # Fix future timestamps by setting them to current time
            if issue.record_id:
                scrobble = Scrobble.objects.get(id=issue.record_id)
                if scrobble.timestamp > timezone.now():
                    scrobble.timestamp = timezone.now()
                    scrobble.save(update_fields=['timestamp'])
                    return True

        elif issue.category == 'data_consistency':
            # Fix invalid MBIDs by clearing them
            if 'invalid MBID format' in issue.message and issue.record_id:
                model_class = {
                    'artist': Artist,
                    'album': Album,
                    'track': Track
                }.get(issue.model_type)

                if model_class:
                    record = model_class.objects.get(id=issue.record_id)
                    record.mbid = None
                    record.save(update_fields=['mbid'])
                    return True

            # Fix invalid URLs by clearing them
            if 'invalid URL' in issue.message and issue.record_id:
                model_class = {
                    'artist': Artist,
                    'album': Album,
                    'track': Track
                }.get(issue.model_type)

                if model_class:
                    record = model_class.objects.get(id=issue.record_id)
                    record.url = None
                    record.save(update_fields=['url'])
                    return True

        elif issue.category == 'orphaned':
            # Fix mismatched track-album relationships
            if 'belongs to album' in issue.message and issue.record_id:
                track = Track.objects.get(id=issue.record_id)
                # Set album to None if it doesn't match the track's artist
                if track.album and track.album.artist != track.artist:
                    track.album = None
                    track.save(update_fields=['album'])
                    return True

        return False

    def _add_issue(self, category: str, severity: str, message: str,
                   model_type: str = None, record_id: int = None,
                   record_details: dict = None, fix_available: bool = False):
        """Add a validation issue to the list."""
        issue = ValidationIssue(
            category=category,
            severity=severity,
            message=message,
            model_type=model_type,
            record_id=record_id,
            record_details=record_details,
            fix_available=fix_available
        )
        self.issues.append(issue)
        self.stats[f'{category}_{severity}'] += 1

    def _generate_report(self):
        """Generate validation report based on output format."""
        if self.output_format == 'json':
            self._generate_json_report()
        else:
            self._generate_text_report()

    def _generate_text_report(self):
        """Generate human-readable text report."""
        if not self.issues:
            self.stdout.write(
                self.style.SUCCESS('No data quality issues found!')
            )
            return

        # Group issues by category and severity
        issues_by_category = defaultdict(list)
        for issue in self.issues:
            issues_by_category[issue.category].append(issue)

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('DATA VALIDATION REPORT')
        self.stdout.write('=' * 60)

        for category, category_issues in issues_by_category.items():
            self.stdout.write(f'\n{category.upper().replace("_", " ")} ({len(category_issues)} issues):')
            self.stdout.write('-' * 40)

            for issue in category_issues:
                severity_style = {
                    'error': self.style.ERROR,
                    'warning': self.style.WARNING,
                    'info': self.style.SUCCESS
                }.get(issue.severity, self.style.SUCCESS)

                self.stdout.write(
                    f'  [{issue.severity.upper()}] {issue.message}'
                )

                if self.verbose and issue.record_details:
                    for key, value in issue.record_details.items():
                        if key != 'duplicate_ids':  # Don't show long lists
                            self.stdout.write(f'    {key}: {value}')

                if issue.fix_available:
                    self.stdout.write('    [FIXABLE]')

    def _generate_json_report(self):
        """Generate JSON format report."""
        report = {
            'validation_summary': {
                'total_issues': len(self.issues),
                'fixable_issues': sum(1 for issue in self.issues if issue.fix_available),
                'fixes_applied': len(self.fixes_applied) if self.fix_mode else 0,
                'categories': dict(self.stats)
            },
            'issues': [issue.to_dict() for issue in self.issues],
            'fixes_applied': [issue.to_dict() for issue in self.fixes_applied] if self.fix_mode else []
        }

        self.stdout.write(json.dumps(report, indent=2, default=str))

    def _print_summary(self):
        """Print validation summary."""
        if self.output_format == 'json':
            return  # Summary is included in JSON

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('VALIDATION SUMMARY')
        self.stdout.write('=' * 60)

        # Count records
        total_artists = Artist.objects.count()
        total_albums = Album.objects.count()
        total_tracks = Track.objects.count()
        total_scrobbles = Scrobble.objects.count()

        self.stdout.write(f'Total Records Validated:')
        self.stdout.write(f'  Artists: {total_artists:,}')
        self.stdout.write(f'  Albums: {total_albums:,}')
        self.stdout.write(f'  Tracks: {total_tracks:,}')
        self.stdout.write(f'  Scrobbles: {total_scrobbles:,}')

        # Issue summary
        self.stdout.write(f'\nIssues Found:')
        error_count = sum(1 for issue in self.issues if issue.severity == 'error')
        warning_count = sum(1 for issue in self.issues if issue.severity == 'warning')
        info_count = sum(1 for issue in self.issues if issue.severity == 'info')

        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(f'  Warnings: {warning_count}')
        self.stdout.write(f'  Info: {info_count}')
        self.stdout.write(f'  Total: {len(self.issues)}')

        if self.fix_mode:
            self.stdout.write(f'\nFixes Applied: {len(self.fixes_applied)}')

        # Data quality score
        total_records = total_artists + total_albums + total_tracks + total_scrobbles
        if total_records > 0:
            quality_score = max(0, (total_records - error_count - warning_count) / total_records * 100)
            self.stdout.write(f'\nData Quality Score: {quality_score:.1f}%')

            if quality_score >= 95:
                self.stdout.write(self.style.SUCCESS('Excellent data quality!'))
            elif quality_score >= 85:
                self.stdout.write(self.style.WARNING('Good data quality with minor issues.'))
            else:
                self.stdout.write(self.style.ERROR('Data quality needs attention.'))

        if error_count == 0:
            self.stdout.write(
                self.style.SUCCESS('\nNo critical errors found!')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'\n{error_count} critical errors need attention.')
            )