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

## Story 1 Completion Status

✅ **Acceptance Criteria Met:**
- [x] Django project created with name "scrobblarr"
- [x] Virtual environment configured with requirements.txt
- [x] Basic Django apps created: `core`, `music`, `stats`
- [x] SQLite database configured
- [x] Django settings properly configured for development
- [x] Initial migration structure created (run `makemigrations` + `migrate`)
- [x] Django admin configured (access at `/admin/` after creating superuser)
- [x] Basic project structure follows Django best practices

## Next Steps

1. Run the setup commands above to complete database initialization
2. Proceed with Story 2: Music Data Models (models are already created)
3. Test the admin interface functionality
4. Begin CSV import command development