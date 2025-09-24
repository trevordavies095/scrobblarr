# Scrobblarr - Product Requirements Document

## 1. Project Overview

### Problem Statement
After 15+ years of using Last.fm with ~150k scrobbles across multiple accounts, there's no unified view of listening history. Historical data is fragmented across different accounts, preventing comprehensive analysis of music listening patterns over time.

### Solution
Scrobblarr is a self-hosted web application that consolidates historical Last.fm data and provides ongoing synchronization with a primary Last.fm account, offering unified music listening analytics. Following the naming convention of popular self-hosted applications (Sonarr, Radarr, etc.), Scrobblarr fits naturally into existing self-hosted media management ecosystems.

### Success Criteria
- All historical scrobble data viewable in one unified Scrobblarr interface
- Core Last.fm statistics functionality replicated
- Automated synchronization with primary Last.fm account
- Self-hostable via Docker with minimal setup complexity, compatible with existing *arr application stacks

## 2. User Stories & Use Cases

### MVP User Stories
1. **Data Import**: As a user, I want to import my consolidated CSV file so that all my historical scrobbles are in the system
2. **Recent Activity**: As a user, I want to see my 10 most recent tracks so I can quickly see what I've been listening to
3. **Top Statistics**: As a user, I want to view top artists, albums, and tracks across different time periods so I can understand my listening patterns
4. **Visual Analytics**: As a user, I want to see a bar chart of my scrobbles over time so I can visualize my listening activity
5. **Artist Deep-dive**: As a user, I want to click on an artist to see their top albums, top tracks, and scrobble history
6. **Album Deep-dive**: As a user, I want to click on an album to see track listings with play counts and scrobble history
7. **Data Sync**: As a user, I want the system to automatically fetch new scrobbles from my primary Last.fm account

## 8. Configuration Management

### 8.1 Environment Variables
- `LASTFM_API_KEY` - Last.fm API key for sync functionality  
- `LASTFM_API_SECRET` - Last.fm API secret
- `SYNC_FREQUENCY` - Sync interval (hourly/daily/manual)
- `TIMEZONE` - User timezone for timestamp display
- `LOG_LEVEL` - Logging verbosity (DEBUG/INFO/WARNING/CRITICAL)

### 8.2 User Preferences
- Default number of items in top lists (10/25/50/100)
- Chart time granularity preferences
- Timestamp display format (relative vs absolute)

## 9. Future Enhancements (Post-MVP)

### 9.1 Deferred Features  
- Interactive charts (click bars to see daily listening details)
- Album artwork integration
- Built-in backup/export functionality for SQLite database
- Advanced filtering and search capabilities
- Listening streaks and milestone tracking
- Raw Last.fm API response storage for debugging

### 9.2 Architectural Considerations
- System optimized for single-user deployment
- Multi-user support not planned (users can deploy separate instances)
- Focus on simplicity over scalability

## 3. Functional Requirements

### 3.1 Data Import
- **CSV Processing**: Import consolidated CSV with columns: `uts,utc_time,artist,artist_mbid,album,album_mbid,track,track_mbid`
- **Data Validation**: Handle missing MBIDs and malformed timestamps
- **Data Strategy**: 
  - Keep artist/album/track names exactly as-is (no normalization)
  - Use MusicBrainz IDs as primary identifiers when available, fallback to text matching when missing
  - No duplicate handling needed (future syncs start from last historical scrobble)
- **Progress Tracking**: Show import progress for large datasets
- **Error Handling**: Log and report any import failures with specific error details

### 3.2 Recent Tracks Display
- Show 10 most recent scrobbles by default
- Display: Track Name, Album, Artist, Timestamp
- Timestamp formatting: flexible (exact time or relative time)
- Real-time updates when new scrobbles are synced

### 3.3 Top Statistics
- **Time Periods**: Last 7 days, Last 30 days, Last 90 days, Last 180 days, Last 365 days, All Time
- **Categories**: Top Artists, Top Albums, Top Tracks
- **Display Options**: 
  - Default to top 10 items
  - Configurable count (10, 25, 50, 100)
  - Show play counts alongside rankings
  - Flat list format (no artist grouping for albums)

### 3.4 Scrobbles Over Time Visualization
- **Bar Chart Features**:
  - X-axis: Time periods
  - Y-axis: Number of scrobbles
  - Time granularity: Yearly (default), Monthly for ranges < 1 year
- **Date Range Options**: Same as top statistics + custom From/To date selector
- **Future Enhancement**: Interactive bars for drill-down

### 3.5 Artist Pages
- Artist name and basic info
- Top albums by that artist (with play counts)
- Top tracks by that artist (with play counts)
- Scrobbles over time chart specific to that artist
- Link back to main statistics

### 3.6 Album Pages
- Album name, artist, and basic info
- Complete track listing with individual play counts
- Scrobbles over time chart specific to that album
- Link to artist page

### 3.7 Last.fm Integration
- **Authentication**: Secure API key storage
- **Delta Sync**: Fetch only new scrobbles since last historical scrobble timestamp
- **Sync Frequency**: Configurable (hourly, daily, manual) via Django-Q background tasks
- **Last.fm Reference**: Store Last.fm scrobble reference ID (timestamp-based) for data traceability
- **Error Handling**: Graceful handling of API rate limits and failures
- **Data Consistency**: No duplicate prevention needed (syncs start from known point)

## 4. Technical Requirements

### 4.1 Architecture
- **Framework**: Django with Django REST Framework
- **Database**: SQLite (single file, perfect for self-hosting)
- **Frontend**: Django templates + htmx, desktop-first with mobile-friendly responsive design
- **Background Tasks**: Django-Q for Last.fm sync scheduling (uses existing database)
- **Charts**: Chart.js for scrobbles over time visualization
- **Deployment**: Single Docker container

### 4.2 Database Schema
```sql
Artists (id, name, mbid, url, created_at)
Albums (id, name, artist_id, mbid, url, created_at)
Tracks (id, name, artist_id, album_id, mbid, url, duration, created_at)
Scrobbles (id, track_id, timestamp, lastfm_reference_id, created_at)
SyncStatus (id, last_sync_timestamp, status, error_message)
```

**Data Linking Strategy:**
- Primary matching via MusicBrainz IDs when available
- Fallback to text-based matching for entities without MBIDs
- Preserve original text exactly as received from sources

### 4.3 API Endpoints
- `GET /api/recent-tracks/` - Recent listening activity
- `GET /api/top-artists/` - Top artists with time period filtering
- `GET /api/top-albums/` - Top albums with time period filtering  
- `GET /api/top-tracks/` - Top tracks with time period filtering
- `GET /api/scrobbles/chart/` - Chart data for visualization
- `GET /api/artists/{id}/` - Artist detail with stats
- `GET /api/albums/{id}/` - Album detail with stats
- `POST /api/import/` - CSV data import
- `POST /api/sync/` - Manual Last.fm sync trigger

### 4.4 Performance Requirements
- Page load times under 2 seconds for typical datasets (150k scrobbles)
- CSV import should handle 150k+ records efficiently
- Database queries optimized with appropriate indexes
- Chart rendering should be responsive for all time ranges

## 5. Non-Functional Requirements

### 5.1 Self-Hosting
- **Docker**: Single container deployment compatible with existing *arr application stacks
- **Configuration**: Environment variables for Last.fm API credentials and preferences
- **Storage**: Persistent volume for SQLite database
- **Documentation**: Clear setup instructions in README following *arr application conventions

### 5.2 Security & Privacy
- Local data storage (no external analytics) - single user deployment
- Secure API key handling via environment variables
- Input validation on all endpoints
- Rate limiting for API endpoints
- Django-Q task queue secured within application boundary

### 5.3 Maintainability
- Clean Django project structure optimized for single-user deployment
- Comprehensive logging (Debug, Info, Warning, Critical levels)
- Database migrations for schema changes
- Modular code for future feature additions
- Django-Q for simplified background task management

### 5.4 User Experience
- Desktop-first responsive design with mobile-friendly layout
- **Navigation Structure**:
  - Top navigation: Home | Recent | Top Artists | Top Albums | Top Tracks | Charts
  - Persistent time period selector on relevant pages
  - Breadcrumb navigation for drill-downs (Home > Artists > Artist Name > Album Name)
- Loading states for long operations (import, chart rendering)
- Error messages that are helpful to users
- Chart.js implementation for interactive and responsive visualizations

## 6. Development Phases

### Phase 1: Core Data Layer
- Django project setup with models
- CSV import functionality
- Basic admin interface for data inspection

### Phase 2: Statistics API
- Core API endpoints for top lists and recent tracks
- Chart data endpoints
- Artist and album detail endpoints

### Phase 3: Web Interface
- Basic templates for all main views
- Chart visualization implementation
- Navigation between artist/album pages

### Phase 4: Last.fm Integration
- API integration for fetching new scrobbles
- Sync mechanism with delta detection
- Automated sync scheduling

### Phase 5: Polish & Docker
- UI/UX improvements
- Docker container creation
- Documentation and deployment guides

## 7. Acceptance Criteria

### MVP Complete When:
- [ ] Can import 150k+ scrobble CSV without errors
- [ ] Recent tracks display shows latest 10 scrobbles
- [ ] All top statistics work across all time periods
- [ ] Scrobbles over time chart displays correctly
- [ ] Artist and album pages show complete information
- [ ] Last.fm sync successfully adds new scrobbles
- [ ] Docker container runs with single command (compatible with existing *arr setups)
- [ ] Basic responsive web interface works on mobile/desktop
- [ ] Scrobblarr branding and UI consistently applied

### Quality Gates:
- [ ] All database queries under 500ms for typical operations
- [ ] CSV import completes within reasonable time (< 5 minutes for 150k records)
- [ ] No data loss during import or sync operations
- [ ] Graceful error handling for all user-facing operations