# Scrobblarr Phase 1 User Stories

## Epic: Core Data Foundation
*Establish the basic data layer and import functionality for Scrobblarr*

---

## Story 1: Django Project Setup
**Priority: P0 (Blocker)**

**As a developer, I want to set up the basic Django project structure so that I have a solid foundation for building Scrobblarr.**

### Acceptance Criteria:
- [ ] Django project created with name "scrobblarr"
- [ ] Virtual environment configured with requirements.txt
- [ ] Basic Django apps created: `core`, `music`, `stats`
- [ ] SQLite database configured
- [ ] Django settings properly configured for development
- [ ] Initial migration created and applied
- [ ] Django admin accessible at /admin/
- [ ] Basic project structure follows Django best practices

### Technical Notes:
- Use Django 4.2+ LTS
- Include Django REST Framework in requirements
- Set up for SQLite initially (production-ready)
- Configure logging framework early
- Include django-extensions for development helpers

---

## Story 2: Music Data Models
**Priority: P0 (Blocker)**

**As a user, I want the system to have proper data models so that my music scrobble data can be stored efficiently and queried effectively.**

### Acceptance Criteria:
- [ ] Artist model with fields: name, mbid, url, created_at
- [ ] Album model with fields: name, artist (FK), mbid, url, created_at
- [ ] Track model with fields: name, artist (FK), album (FK), mbid, url, duration, created_at
- [ ] Scrobble model with fields: track (FK), timestamp, lastfm_reference_id, created_at
- [ ] SyncStatus model for tracking Last.fm sync state
- [ ] All models have proper __str__ methods
- [ ] Database indexes on frequently queried fields (artist name, timestamp)
- [ ] Models registered in Django admin with basic list/filter views

### Technical Notes:
- Use UUIDs for primary keys or stick with Django default integers
- Consider nullable foreign keys for tracks without album data
- Add database constraints for data integrity
- Use timezone-aware datetime fields
- MBID fields should be optional (nullable=True)

---

## Story 3: CSV Import Command
**Priority: P0 (Blocker)**

**As a user, I want to import my consolidated Last.fm CSV file so that all my historical scrobble data is available in Scrobblarr.**

### Acceptance Criteria:
- [ ] Django management command `python manage.py import_scrobbles <csv_file>`
- [ ] Parses CSV with columns: uts, utc_time, artist, artist_mbid, album, album_mbid, track, track_mbid
- [ ] Creates Artist records (using MBID when available, text matching as fallback)
- [ ] Creates Album records (linked to artists)
- [ ] Creates Track records (linked to artists and albums)
- [ ] Creates Scrobble records with proper timestamps
- [ ] Progress indicator shows import status (every 1000 records)
- [ ] Handles missing MBID values gracefully
- [ ] Skips malformed rows with logging
- [ ] Reports final import statistics (total imported, skipped, errors)
- [ ] Can handle 150k+ records without memory issues

### Technical Notes:
- Use Django's bulk_create for performance
- Implement get_or_create logic for artists/albums/tracks
- Convert unix timestamp (uts) to Django datetime
- Use transactions for data integrity
- Log errors with row numbers for debugging
- Consider using csv.DictReader for cleaner parsing

---

## Story 4: Data Validation and Integrity
**Priority: P1 (High)**

**As a user, I want the system to validate my imported data so that I can trust the accuracy of my statistics and identify any data issues.**

### Acceptance Criteria:
- [ ] Validation command `python manage.py validate_data`
- [ ] Checks for orphaned records (tracks without artists, etc.)
- [ ] Identifies duplicate scrobbles (same track + timestamp)
- [ ] Reports artists/albums/tracks with missing names
- [ ] Validates timestamp ranges (no future dates, reasonable past dates)
- [ ] Provides summary of data quality issues
- [ ] Optional `--fix` flag to attempt automatic corrections
- [ ] Logs all validation issues with specific record IDs

### Technical Notes:
- Use Django's database constraint checking
- Implement custom validation rules for music data
- Consider data quality metrics (completeness, consistency)
- Provide actionable error messages

---

## Story 5: Admin Interface Enhancement
**Priority: P1 (High)**

**As a user, I want an enhanced admin interface so that I can inspect and manage my imported data easily.**

### Acceptance Criteria:
- [ ] Artist admin: list view with name, MBID, track count, recent activity
- [ ] Album admin: list view with name, artist, track count, scrobble count
- [ ] Track admin: list view with name, artist, album, scrobble count
- [ ] Scrobble admin: list view with track, artist, timestamp
- [ ] Search functionality on artist/album/track names
- [ ] Filters for date ranges, missing MBIDs, high play counts
- [ ] Pagination for large datasets
- [ ] Bulk actions for common operations
- [ ] Related object links (click artist to see their albums)

### Technical Notes:
- Use list_select_related for query optimization
- Add custom admin actions for data management
- Consider read-only fields for computed values
- Use Django admin's date hierarchy for scrobbles

---

## Story 6: Basic API Endpoints
**Priority: P1 (High)**

**As a developer, I want basic API endpoints so that the frontend can access scrobble data and statistics.**

### Acceptance Criteria:
- [ ] `/api/artists/` - List artists with basic info and scrobble counts
- [ ] `/api/albums/` - List albums with artist info and scrobble counts
- [ ] `/api/tracks/` - List tracks with artist/album info and scrobble counts
- [ ] `/api/scrobbles/` - List scrobbles with related track/artist/album data
- [ ] All endpoints support pagination
- [ ] All endpoints return JSON with consistent structure
- [ ] Basic filtering by date range (?from_date=2024-01-01&to_date=2024-12-31)
- [ ] Endpoints include total count metadata
- [ ] Proper HTTP status codes and error handling

### Technical Notes:
- Use Django REST Framework serializers
- Implement select_related/prefetch_related for performance
- Set reasonable default page sizes (50-100 items)
- Use ISO format for dates in API
- Consider using DRF's filter backends

---

## Story 7: Data Statistics Calculations
**Priority: P2 (Medium)**

**As a user, I want the system to calculate basic statistics from my data so that I can verify the import was successful and get initial insights.**

### Acceptance Criteria:
- [ ] Management command `python manage.py calculate_stats`
- [ ] Calculates total scrobbles, unique tracks, unique artists, unique albums
- [ ] Finds most played artist, album, and track
- [ ] Calculates date range of scrobbles (first and last)
- [ ] Shows scrobbles per year/month breakdown
- [ ] Outputs results to console and optionally to JSON file
- [ ] Performance optimized for large datasets

### Technical Notes:
- Use Django ORM aggregation functions
- Consider caching results for expensive calculations
- Use database-level calculations where possible
- Format output for human readability

---

## Story 8: Error Handling and Logging
**Priority: P2 (Medium)**

**As a user, I want comprehensive error handling and logging so that I can troubleshoot issues and monitor system health.**

### Acceptance Criteria:
- [ ] Structured logging configuration (DEBUG, INFO, WARNING, ERROR)
- [ ] Import process logs progress, errors, and warnings
- [ ] API endpoints log requests and errors
- [ ] Database errors are caught and logged with context
- [ ] Log rotation configured for production use
- [ ] Console output for development, file output for production
- [ ] Critical errors include stack traces
- [ ] Performance metrics logged for expensive operations

### Technical Notes:
- Use Python's logging module with proper formatters
- Configure different log levels for different modules
- Consider using structured logging (JSON format)
- Include request IDs for API call tracing

---

## Definition of Done for Phase 1:
- [ ] All user stories completed with acceptance criteria met
- [ ] Code reviewed and follows Django best practices
- [ ] Basic tests written for critical functionality
- [ ] Documentation updated (README with setup instructions)
- [ ] Database migrations created and tested
- [ ] Import process successfully handles 150k+ scrobble CSV
- [ ] Admin interface functional for data inspection
- [ ] API endpoints return expected data structure
- [ ] Logging properly configured and functional

## Handoff Notes for Claude Code:

**Key Technical Decisions:**
- Django 4.2+ with DRF
- SQLite database (single file)
- Bulk operations for CSV import performance
- MBID-first matching with text fallback
- Preserve original text exactly as imported

**CSV Format Reference:**
```
uts,utc_time,artist,artist_mbid,album,album_mbid,track,track_mbid
1640995200,2022-01-01 00:00:00,The Beatles,b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d,Abbey Road,729b68b1-c551-4d38-acc3-e5e1e17e1de8,Come Together,60dfa5ec-84b7-4d30-b1f5-ae5af27a9f29
```

**Priority for Implementation:**
1. Start with Story 1 & 2 (project setup and models)
2. Move to Story 3 (CSV import) - this is the core functionality
3. Add Story 4 & 5 (validation and admin) for data inspection
4. Implement Story 6 (API endpoints) for future frontend work
5. Add Stories 7 & 8 (stats and logging) for completeness

**Success Metric:**
Phase 1 is complete when a user can run the import command on their 150k scrobble CSV and then use the admin interface to browse and verify their imported data.