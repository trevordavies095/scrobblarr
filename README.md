# Scrobblarr

A self-hosted web application for consolidating and analyzing Last.fm music listening data.

## Development Setup

### Prerequisites
- Python 3.8+
- pip or pipenv

### Installation

1. **Clone or navigate to the project directory**
   ```bash
   cd scrobblarr
   ```

2. **Create and activate a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   - Copy `.env` file and update as needed:
     ```bash
     cp .env .env.local
     # Edit .env.local with your settings
     ```

5. **Database Setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create Superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

8. **Access the Application**
   - Web Interface: http://127.0.0.1:8000/
   - Admin Interface: http://127.0.0.1:8000/admin/
   - API: http://127.0.0.1:8000/api/

## Project Structure

```
scrobblarr/
├── core/           # Base models and utilities
├── music/          # Music data models (Artist, Album, Track, Scrobble)
├── stats/          # Statistics and API endpoints
├── scrobblarr/     # Main Django project settings
├── manage.py       # Django management script
├── requirements.txt # Python dependencies
└── .env           # Environment configuration
```

## Story 1, 2 & 3 Completion Status

✅ **Story 1 - Django Project Setup (Complete):**
- [x] Django project created with name "scrobblarr"
- [x] Virtual environment configured with requirements.txt
- [x] Basic Django apps created: `core`, `music`, `stats`
- [x] SQLite database configured
- [x] Django settings properly configured for development
- [x] Initial migration structure created (run `makemigrations` + `migrate`)
- [x] Django admin configured (access at `/admin/` after creating superuser)
- [x] Basic project structure follows Django best practices

✅ **Story 2 - Music Data Models (Complete):**
- [x] Artist model with name, mbid, url, created_at fields + validation
- [x] Album model with name, artist (FK), mbid, url, created_at fields + constraints
- [x] Track model with name, artist (FK), album (FK), mbid, url, duration, created_at fields
- [x] Scrobble model with track (FK), timestamp, lastfm_reference_id, created_at fields
- [x] SyncStatus model for tracking Last.fm sync state with management methods
- [x] All models have proper __str__ methods and helper methods
- [x] Database indexes and constraints on frequently queried fields
- [x] Enhanced admin interface with calculated fields, counts, and navigation links
- [x] MBID validation with proper UUID format checking
- [x] Comprehensive model tests covering all functionality

✅ **Story 3 - CSV Import Command (Complete):**
- [x] Django management command `python manage.py import_scrobbles <csv_file>`
- [x] Parses CSV with expected columns: uts, utc_time, artist, artist_mbid, album, album_mbid, track, track_mbid
- [x] Creates Artist, Album, Track, and Scrobble records with proper relationships
- [x] Uses MBID when available, text matching as fallback
- [x] Progress indicator shows import status (every 1000 records)
- [x] Handles missing MBID values and empty album names gracefully
- [x] Skips malformed rows with detailed logging and row numbers
- [x] Reports final import statistics (total imported, skipped, errors)
- [x] Handles 150k+ records efficiently with bulk operations and batching
- [x] Command options: --batch-size, --dry-run, --verbose
- [x] Comprehensive error handling and validation
- [x] Full test suite covering all import scenarios

## CSV Import Usage

Import your Last.fm scrobble data:
```bash
# Basic import
python manage.py import_scrobbles your_scrobbles.csv

# Test import without saving data
python manage.py import_scrobbles your_scrobbles.csv --dry-run

# Import with custom batch size and verbose output
python manage.py import_scrobbles your_scrobbles.csv --batch-size=500 --verbose
```

Expected CSV format:
```csv
uts,utc_time,artist,artist_mbid,album,album_mbid,track,track_mbid
1640995200,2022-01-01 00:00:00,The Beatles,b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d,Abbey Road,729b68b1-c551-4d38-acc3-e5e1e17e1de8,Come Together,60dfa5ec-84b7-4d30-b1f5-ae5af27a9f29
```

## Next Steps

1. Run the setup commands above to complete database initialization
2. Import your CSV data using the import_scrobbles command
3. Explore your data using the Django admin interface
4. Run tests: `python manage.py test music.tests`
5. Proceed with Story 4: Data Validation and Integrity