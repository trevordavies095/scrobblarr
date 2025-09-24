import csv
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from music.models import Artist, Album, Track, Scrobble


class Command(BaseCommand):
    help = 'Import scrobble data from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing scrobble data'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process in each batch (default: 1000)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and validate the file without importing data'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress information'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        verbose = options['verbose']

        # Validate file exists and is readable
        if not os.path.exists(csv_file):
            raise CommandError(f'File "{csv_file}" does not exist.')

        if not os.path.isfile(csv_file):
            raise CommandError(f'"{csv_file}" is not a file.')

        if not os.access(csv_file, os.R_OK):
            raise CommandError(f'File "{csv_file}" is not readable.')

        # Initialize counters
        total_processed = 0
        total_imported = 0
        total_skipped = 0
        total_errors = 0

        # Track created entities to avoid duplicate lookups
        artist_cache = {}
        album_cache = {}
        track_cache = {}

        self.stdout.write(
            self.style.SUCCESS(f'Starting import from "{csv_file}"')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be imported')
            )

        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                # Detect delimiter and validate headers
                sample = file.read(1024)
                file.seek(0)

                # Try to detect CSV dialect
                try:
                    dialect = csv.Sniffer().sniff(sample)
                    reader = csv.DictReader(file, dialect=dialect)
                except:
                    # Fallback to default dialect
                    reader = csv.DictReader(file)

                # Validate expected columns
                expected_columns = {
                    'uts', 'utc_time', 'artist', 'artist_mbid',
                    'album', 'album_mbid', 'track', 'track_mbid'
                }

                if not reader.fieldnames:
                    raise CommandError('CSV file appears to be empty or invalid')

                missing_columns = expected_columns - set(reader.fieldnames)
                if missing_columns:
                    raise CommandError(
                        f'Missing required columns: {", ".join(missing_columns)}'
                    )

                # Process records in batches
                batch_records = []

                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    total_processed += 1

                    try:
                        # Validate and process row
                        processed_row = self._process_row(row, row_num)
                        if processed_row:
                            batch_records.append(processed_row)

                            # Process batch when it reaches batch_size
                            if len(batch_records) >= batch_size:
                                imported, errors = self._process_batch(
                                    batch_records, artist_cache, album_cache,
                                    track_cache, dry_run, verbose
                                )
                                total_imported += imported
                                total_errors += errors
                                batch_records = []

                                # Progress reporting
                                if total_processed % 1000 == 0:
                                    self.stdout.write(
                                        f'Processed {total_processed:,} records '
                                        f'(imported: {total_imported:,}, '
                                        f'errors: {total_errors:,})'
                                    )
                        else:
                            total_skipped += 1

                    except Exception as e:
                        total_errors += 1
                        self.stderr.write(
                            f'Error processing row {row_num}: {str(e)}'
                        )
                        if verbose:
                            self.stderr.write(f'Row data: {row}')

                # Process remaining records in final batch
                if batch_records:
                    imported, errors = self._process_batch(
                        batch_records, artist_cache, album_cache,
                        track_cache, dry_run, verbose
                    )
                    total_imported += imported
                    total_errors += errors

        except Exception as e:
            raise CommandError(f'Error reading CSV file: {str(e)}')

        # Final report
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 50))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f'Total records processed: {total_processed:,}')
        self.stdout.write(f'Successfully imported: {total_imported:,}')
        self.stdout.write(f'Skipped (invalid data): {total_skipped:,}')
        self.stdout.write(f'Errors encountered: {total_errors:,}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDRY RUN COMPLETE - No data was imported')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nImport completed successfully!')
            )

    def _process_row(self, row: Dict[str, str], row_num: int) -> Optional[Dict[str, Any]]:
        """Process and validate a single CSV row."""
        # Check for required fields
        if not row.get('artist', '').strip():
            self.stderr.write(f'Row {row_num}: Missing artist name')
            return None

        if not row.get('track', '').strip():
            self.stderr.write(f'Row {row_num}: Missing track name')
            return None

        if not row.get('uts', '').strip():
            self.stderr.write(f'Row {row_num}: Missing timestamp')
            return None

        # Convert unix timestamp to datetime
        try:
            uts = int(row['uts'])
            timestamp = datetime.fromtimestamp(uts, tz=timezone.utc)

            # Validate timestamp is reasonable (not in future, not before 1970)
            now = timezone.now()
            if timestamp > now:
                self.stderr.write(f'Row {row_num}: Timestamp is in the future')
                return None

            if timestamp.year < 1970:
                self.stderr.write(f'Row {row_num}: Timestamp is before 1970')
                return None

        except (ValueError, OSError) as e:
            self.stderr.write(f'Row {row_num}: Invalid timestamp "{row.get("uts")}": {e}')
            return None

        # Clean and validate MBID fields (should be UUID format or empty)
        artist_mbid = self._clean_mbid(row.get('artist_mbid', ''))
        album_mbid = self._clean_mbid(row.get('album_mbid', ''))
        track_mbid = self._clean_mbid(row.get('track_mbid', ''))

        # Clean text fields
        artist_name = row['artist'].strip()
        album_name = row.get('album', '').strip() or None
        track_name = row['track'].strip()

        return {
            'artist_name': artist_name,
            'artist_mbid': artist_mbid,
            'album_name': album_name,
            'album_mbid': album_mbid,
            'track_name': track_name,
            'track_mbid': track_mbid,
            'timestamp': timestamp,
            'row_num': row_num
        }

    def _clean_mbid(self, mbid: str) -> Optional[str]:
        """Clean and validate MBID field."""
        if not mbid or not mbid.strip():
            return None

        mbid = mbid.strip().lower()

        # Basic UUID format validation (36 characters, proper hyphens)
        if len(mbid) == 36 and mbid.count('-') == 4:
            return mbid

        # If it doesn't look like a UUID, treat as invalid
        return None

    def _process_batch(self, batch_records: list, artist_cache: dict,
                      album_cache: dict, track_cache: dict, dry_run: bool,
                      verbose: bool) -> Tuple[int, int]:
        """Process a batch of records with database operations."""
        imported = 0
        errors = 0

        if dry_run:
            return len(batch_records), 0

        try:
            with transaction.atomic():
                scrobbles_to_create = []

                for record in batch_records:
                    try:
                        # Get or create artist
                        artist = self._get_or_create_artist(
                            record['artist_name'],
                            record['artist_mbid'],
                            artist_cache
                        )

                        # Get or create album (if specified)
                        album = None
                        if record['album_name']:
                            album = self._get_or_create_album(
                                record['album_name'],
                                record['album_mbid'],
                                artist,
                                album_cache
                            )

                        # Get or create track
                        track = self._get_or_create_track(
                            record['track_name'],
                            record['track_mbid'],
                            artist,
                            album,
                            track_cache
                        )

                        # Prepare scrobble for bulk creation
                        scrobbles_to_create.append(
                            Scrobble(
                                track=track,
                                timestamp=record['timestamp']
                            )
                        )

                    except Exception as e:
                        errors += 1
                        self.stderr.write(
                            f'Error processing record from row {record["row_num"]}: {str(e)}'
                        )

                # Bulk create scrobbles, handling duplicates
                if scrobbles_to_create:
                    try:
                        # Remove within-batch duplicates first
                        seen_in_batch = set()
                        unique_scrobbles = []

                        for scrobble in scrobbles_to_create:
                            scrobble_key = (scrobble.track.id, scrobble.timestamp)
                            if scrobble_key not in seen_in_batch:
                                seen_in_batch.add(scrobble_key)
                                unique_scrobbles.append(scrobble)

                        # Check for existing scrobbles in database
                        final_scrobbles = []
                        for scrobble in unique_scrobbles:
                            existing = Scrobble.objects.filter(
                                track=scrobble.track,
                                timestamp=scrobble.timestamp
                            ).exists()
                            if not existing:
                                final_scrobbles.append(scrobble)

                        if final_scrobbles:
                            Scrobble.objects.bulk_create(final_scrobbles)

                        imported = len(final_scrobbles)

                    except Exception as e:
                        self.stderr.write(f'Error bulk creating scrobbles: {str(e)}')
                        errors += len(scrobbles_to_create)
                        imported = 0

        except Exception as e:
            self.stderr.write(f'Transaction error: {str(e)}')
            errors = len(batch_records)

        return imported, errors

    def _get_or_create_artist(self, name: str, mbid: Optional[str],
                             cache: dict) -> Artist:
        """Get or create artist, using cache for performance."""
        cache_key = f"{name}|{mbid or ''}"

        if cache_key in cache:
            return cache[cache_key]

        # Try to find by MBID first, then by name
        if mbid:
            artist, created = Artist.objects.get_or_create(
                mbid=mbid,
                defaults={'name': name}
            )
        else:
            artist, created = Artist.objects.get_or_create(
                name=name
            )

        cache[cache_key] = artist
        return artist

    def _get_or_create_album(self, name: str, mbid: Optional[str],
                            artist: Artist, cache: dict) -> Album:
        """Get or create album, using cache for performance."""
        cache_key = f"{artist.id}|{name}|{mbid or ''}"

        if cache_key in cache:
            return cache[cache_key]

        # Try to find by MBID first, then by name + artist
        if mbid:
            album, created = Album.objects.get_or_create(
                mbid=mbid,
                defaults={'name': name, 'artist': artist}
            )
        else:
            album, created = Album.objects.get_or_create(
                name=name,
                artist=artist
            )

        cache[cache_key] = album
        return album

    def _get_or_create_track(self, name: str, mbid: Optional[str],
                            artist: Artist, album: Optional[Album],
                            cache: dict) -> Track:
        """Get or create track, using cache for performance."""
        cache_key = f"{artist.id}|{album.id if album else 'None'}|{name}|{mbid or ''}"

        if cache_key in cache:
            return cache[cache_key]

        # Try to find by MBID first, then by name + artist + album
        if mbid:
            track, created = Track.objects.get_or_create(
                mbid=mbid,
                defaults={
                    'name': name,
                    'artist': artist,
                    'album': album
                }
            )
        else:
            track, created = Track.objects.get_or_create(
                name=name,
                artist=artist,
                album=album
            )

        cache[cache_key] = track
        return track