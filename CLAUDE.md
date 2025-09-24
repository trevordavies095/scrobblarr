# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scrobblarr is a self-hosted web application for consolidating and analyzing Last.fm music listening data. It's designed to import historical scrobbles from CSV files and provide unified analytics similar to Last.fm, with ongoing synchronization capabilities.

## Architecture

**Framework**: Django with Django REST Framework
**Database**: SQLite (single file for self-hosting)
**Frontend**: Django templates + htmx (desktop-first, mobile-friendly)
**Background Tasks**: Django-Q for Last.fm sync scheduling
**Charts**: Chart.js for visualizations
**Deployment**: Single Docker container

## Data Model Structure

The core data model follows this hierarchy:
- **Artists** (name, mbid, url)
- **Albums** (name, artist_id, mbid, url)
- **Tracks** (name, artist_id, album_id, mbid, url, duration)
- **Scrobbles** (track_id, timestamp, lastfm_reference_id)
- **SyncStatus** (last_sync_timestamp, status, error_message)

**Important Data Strategy**:
- Keep artist/album/track names exactly as-is (no normalization)
- Use MusicBrainz IDs as primary identifiers when available
- Fall back to text matching when MBIDs are missing
- No duplicate handling needed for imports

## Development Commands

### Setup (First Time)
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create database and apply migrations
python manage.py makemigrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Development Commands
```bash
# Import historical scrobble data (coming in Story 3)
python manage.py import_scrobbles <csv_file>

# Validate imported data integrity (coming in Story 4)
python manage.py validate_data

# Calculate and display statistics (coming in Story 7)
python manage.py calculate_stats

# Standard Django commands
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
python manage.py shell
```

## CSV Import Format

The system expects consolidated Last.fm CSV exports with these columns:
```
uts,utc_time,artist,artist_mbid,album,album_mbid,track,track_mbid
```

Import process should handle:
- 150k+ records efficiently using bulk operations
- Missing MBID values gracefully
- Progress tracking and error reporting
- Transaction-based data integrity

## API Endpoints (Planned)

Core REST API structure:
- `GET /api/recent-tracks/` - Recent listening activity
- `GET /api/top-artists/` - Top artists with time period filtering
- `GET /api/top-albums/` - Top albums with time period filtering
- `GET /api/top-tracks/` - Top tracks with time period filtering
- `GET /api/scrobbles/chart/` - Chart data for visualizations
- `GET /api/artists/{id}/` - Artist detail with statistics
- `GET /api/albums/{id}/` - Album detail with track listings
- `POST /api/import/` - Trigger CSV import
- `POST /api/sync/` - Manual Last.fm synchronization

## Configuration

Environment variables for deployment:
- `LASTFM_API_KEY` - Last.fm API key for sync functionality
- `LASTFM_API_SECRET` - Last.fm API secret
- `SYNC_FREQUENCY` - Sync interval (hourly/daily/manual)
- `TIMEZONE` - User timezone for timestamp display
- `LOG_LEVEL` - Logging verbosity

## Development Phase Structure

**Phase 1**: Core data layer, CSV import, Django admin
**Phase 2**: Statistics API endpoints
**Phase 3**: Web interface with Chart.js visualizations
**Phase 4**: Last.fm integration and sync mechanism
**Phase 5**: Docker containerization and deployment

## Key Technical Decisions

- SQLite for simplicity and self-hosting compatibility
- Single-user deployment model (no multi-tenancy)
- Desktop-first responsive design
- Bulk database operations for performance with large datasets
- Django-Q for background sync tasks (reuses existing database)
- Preserve original text exactly as received from data sources