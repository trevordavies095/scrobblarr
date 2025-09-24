# Scrobblarr Phase 2 User Stories

## Epic: Statistics API & Core Functionality  
*Build the core Last.fm-like statistics and API endpoints that power the Scrobblarr experience*

---

## Story 9: Recent Tracks API
**Priority: P0 (Blocker)**

**As a user, I want to see my recent listening activity so that I can quickly see what I've been listening to lately.**

### Acceptance Criteria:
- [ ] API endpoint `/api/recent-tracks/` returns last 10 scrobbles by default
- [ ] Response includes: track name, artist name, album name, timestamp
- [ ] Supports `?limit=N` parameter (max 50, min 1)
- [ ] Results ordered by timestamp descending (most recent first)  
- [ ] Timestamps returned in ISO 8601 format
- [ ] Includes pagination metadata (has_next, has_previous)
- [ ] Handles empty results gracefully
- [ ] Response time under 200ms for typical datasets

### API Response Example:
```json
{
  "results": [
    {
      "track": "Come Together",
      "artist": "The Beatles", 
      "album": "Abbey Road",
      "timestamp": "2024-01-15T14:30:00Z"
    }
  ],
  "count": 10,
  "has_next": true,
  "has_previous": false
}
```

### Technical Notes:
- Use select_related for artist/album to avoid N+1 queries
- Consider caching for frequently accessed recent tracks
- Include proper error handling for invalid limit values

---

## Story 10: Top Artists API with Time Filtering
**Priority: P0 (Blocker)**

**As a user, I want to see my top artists across different time periods so that I can understand my listening patterns over time.**

### Acceptance Criteria:
- [ ] API endpoint `/api/top-artists/` returns top artists with play counts
- [ ] Time period filters: `7d`, `30d`, `90d`, `180d`, `365d`, `all` (default: `all`)
- [ ] Query parameter: `?period=30d&limit=10`
- [ ] Default limit: 10, configurable up to 100
- [ ] Results ordered by scrobble count descending
- [ ] Response includes: artist name, scrobble count, mbid (if available)
- [ ] Handles invalid time periods gracefully
- [ ] Supports custom date ranges via `?from_date=2024-01-01&to_date=2024-12-31`
- [ ] Performance optimized for large datasets

### API Response Example:
```json
{
  "period": "30d",
  "results": [
    {
      "artist": "The Beatles",
      "scrobble_count": 145,
      "mbid": "b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
    }
  ],
  "count": 10,
  "total_scrobbles": 1250
}
```

### Technical Notes:
- Use database-level date filtering for performance
- Consider adding database indexes on timestamp + artist_id
- Cache expensive aggregation queries
- Use timezone-aware date calculations

---

## Story 11: Top Albums API with Time Filtering
**Priority: P0 (Blocker)**

**As a user, I want to see my top albums across different time periods so that I can track my album listening patterns.**

### Acceptance Criteria:
- [ ] API endpoint `/api/top-albums/` returns top albums with play counts
- [ ] Same time period filtering as top artists
- [ ] Flat list of albums (not grouped by artist)
- [ ] Response includes: album name, artist name, scrobble count, mbid
- [ ] Results ordered by scrobble count descending
- [ ] Default limit: 10, configurable up to 100
- [ ] Handles albums with missing names gracefully
- [ ] Performance optimized with proper joins

### API Response Example:
```json
{
  "period": "90d",
  "results": [
    {
      "album": "Abbey Road",
      "artist": "The Beatles",
      "scrobble_count": 89,
      "mbid": "729b68b1-c551-4d38-acc3-e5e1e1d2600d"
    }
  ],
  "count": 10,
  "total_scrobbles": 850
}
```

### Technical Notes:
- Use select_related for artist information
- Handle tracks without album associations
- Consider separate endpoint for "Singles/Unknown Albums"

---

## Story 12: Top Tracks API with Time Filtering
**Priority: P0 (Blocker)**

**As a user, I want to see my top tracks across different time periods so that I can identify my most-played songs.**

### Acceptance Criteria:
- [ ] API endpoint `/api/top-tracks/` returns top tracks with play counts
- [ ] Same time period filtering as other top endpoints
- [ ] Response includes: track name, artist name, album name, scrobble count, mbid
- [ ] Results ordered by scrobble count descending
- [ ] Default limit: 10, configurable up to 100
- [ ] Handles tracks with missing album information
- [ ] Performance optimized for large datasets

### API Response Example:
```json
{
  "period": "7d",
  "results": [
    {
      "track": "Come Together",
      "artist": "The Beatles",
      "album": "Abbey Road", 
      "scrobble_count": 12,
      "mbid": "60dfa5ec-84b7-4d30-b1f5-ae5af27a9f29"
    }
  ],
  "count": 10,
  "total_scrobbles": 95
}
```

### Technical Notes:
- Join with both artist and album tables
- Consider performance implications of triple joins
- Cache popular time period queries

---

## Story 13: Scrobbles Over Time Chart Data API
**Priority: P1 (High)**

**As a user, I want chart data for my scrobbles over time so that I can visualize my listening activity patterns.**

### Acceptance Criteria:
- [ ] API endpoint `/api/scrobbles/chart/` returns time-series data
- [ ] Time period filters: same as top lists plus custom date ranges
- [ ] Auto-granularity: yearly for >1 year periods, monthly for <1 year
- [ ] Manual granularity override: `?granularity=daily|monthly|yearly`
- [ ] Response optimized for Chart.js consumption
- [ ] Handles periods with no scrobbles (returns 0)
- [ ] Maximum data points limited to prevent performance issues
- [ ] Timezone handling for accurate date bucketing

### API Response Example:
```json
{
  "period": "365d",
  "granularity": "monthly",
  "data": [
    {
      "period": "2024-01",
      "scrobble_count": 1250,
      "start_date": "2024-01-01",
      "end_date": "2024-01-31"
    }
  ],
  "total_scrobbles": 15000
}
```

### Technical Notes:
- Use database date truncation functions (DATE_TRUNC)
- Consider pre-computing popular aggregations
- Optimize for Chart.js label and data format
- Handle timezone conversions properly

---

## Story 14: Artist Detail API
**Priority: P1 (High)**

**As a user, I want detailed information about a specific artist so that I can drill down into my listening history for that artist.**

### Acceptance Criteria:
- [ ] API endpoint `/api/artists/{id}/` returns artist details
- [ ] Basic info: name, mbid, total scrobbles, first/last scrobble dates
- [ ] Top albums by that artist (with scrobble counts)
- [ ] Top tracks by that artist (with scrobble counts)
- [ ] Scrobbles over time data for chart visualization
- [ ] Time period filtering for top albums/tracks
- [ ] Supports both internal ID and MBID lookup
- [ ] 404 handling for non-existent artists
- [ ] Performance optimized with minimal queries

### API Response Example:
```json
{
  "artist": {
    "name": "The Beatles",
    "mbid": "b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d",
    "total_scrobbles": 2150,
    "first_scrobble": "2009-05-15T10:30:00Z",
    "last_scrobble": "2024-01-15T14:30:00Z"
  },
  "top_albums": [
    {
      "album": "Abbey Road",
      "scrobble_count": 189
    }
  ],
  "top_tracks": [
    {
      "track": "Come Together",
      "album": "Abbey Road",
      "scrobble_count": 45
    }
  ],
  "chart_data": { /* same format as chart API */ }
}
```

### Technical Notes:
- Use slug or MBID in URL for better SEO
- Prefetch related data to minimize queries
- Consider caching artist pages
- Handle artists with missing MBIDs

---

## Story 15: Album Detail API  
**Priority: P1 (High)**

**As a user, I want detailed information about a specific album so that I can see track-by-track listening statistics.**

### Acceptance Criteria:
- [ ] API endpoint `/api/albums/{id}/` returns album details
- [ ] Basic info: name, artist, mbid, total scrobbles, first/last scrobble dates
- [ ] Complete track listing with individual scrobble counts
- [ ] Track list ordered by original album order (or scrobble count if no order available)
- [ ] Scrobbles over time data for the album
- [ ] Link to parent artist information
- [ ] 404 handling for non-existent albums
- [ ] Performance optimized track list queries

### API Response Example:
```json
{
  "album": {
    "name": "Abbey Road",
    "artist": "The Beatles",
    "mbid": "729b68b1-c551-4d38-acc3-e5e1e1d2600d",
    "total_scrobbles": 189,
    "first_scrobble": "2009-06-01T12:00:00Z",
    "last_scrobble": "2024-01-10T16:45:00Z"
  },
  "tracks": [
    {
      "track": "Come Together",
      "scrobble_count": 45,
      "mbid": "60dfa5ec-84b7-4d30-b1f5-ae5af27a9f29"
    }
  ],
  "chart_data": { /* album-specific chart data */ }
}
```

### Technical Notes:
- Efficient track list queries with scrobble counts
- Consider track ordering strategies
- Handle albums with missing track data
- Optimize related artist data fetching

---

## Story 16: Statistics Summary API
**Priority: P2 (Medium)**

**As a user, I want a summary of my overall listening statistics so that I can get a quick overview of my music library.**

### Acceptance Criteria:
- [ ] API endpoint `/api/stats/summary/` returns overall statistics
- [ ] Total counts: scrobbles, unique artists, unique albums, unique tracks
- [ ] Date range: first scrobble date, last scrobble date, total days
- [ ] Top overall: most played artist, album, track (all-time)
- [ ] Listening averages: scrobbles per day, per month, per year
- [ ] Recent activity: scrobbles in last 7/30 days
- [ ] Performance optimized with caching

### API Response Example:
```json
{
  "totals": {
    "scrobbles": 150000,
    "artists": 2150,
    "albums": 5230,
    "tracks": 18750
  },
  "date_range": {
    "first_scrobble": "2009-03-15T10:00:00Z",
    "last_scrobble": "2024-01-15T14:30:00Z",
    "total_days": 5450
  },
  "top_all_time": {
    "artist": "The Beatles",
    "album": "Abbey Road",
    "track": "Come Together"
  },
  "averages": {
    "per_day": 27.5,
    "per_month": 833,
    "per_year": 10000
  }
}
```

### Technical Notes:
- Use database aggregation functions
- Cache expensive calculations
- Consider pre-computing summary stats
- Handle division by zero for averages

---

## Story 17: API Error Handling & Validation
**Priority: P2 (Medium)**

**As a developer, I want consistent error handling across all APIs so that the frontend can properly handle and display errors.**

### Acceptance Criteria:
- [ ] Consistent error response format across all endpoints
- [ ] Proper HTTP status codes (400, 404, 422, 500)
- [ ] Validation errors for invalid parameters (dates, limits, periods)
- [ ] Rate limiting on expensive endpoints
- [ ] Request logging with performance metrics
- [ ] Helpful error messages for developers
- [ ] API documentation with error examples

### Error Response Format:
```json
{
  "error": {
    "code": "INVALID_TIME_PERIOD",
    "message": "Time period '45d' is not supported. Use: 7d, 30d, 90d, 180d, 365d, all",
    "details": {
      "parameter": "period",
      "provided": "45d",
      "allowed": ["7d", "30d", "90d", "180d", "365d", "all"]
    }
  }
}
```

### Technical Notes:
- Use DRF's exception handling
- Create custom exception classes
- Add parameter validation decorators
- Log errors with request context

---

## Story 18: API Performance Optimization
**Priority: P2 (Medium)**

**As a user, I want fast API responses so that the Scrobblarr interface feels responsive.**

### Acceptance Criteria:
- [ ] All API endpoints respond in under 500ms for typical datasets
- [ ] Database query optimization with explain analysis
- [ ] Proper database indexes on frequently queried fields
- [ ] Query result caching for expensive operations
- [ ] Pagination for all list endpoints
- [ ] Connection pooling configured
- [ ] API response compression enabled
- [ ] Performance monitoring and alerting setup

### Technical Notes:
- Use select_related/prefetch_related appropriately
- Add database indexes: (timestamp), (artist_id, timestamp), etc.
- Implement Redis caching for expensive queries
- Use database query logging in development
- Consider read replicas for heavy read workloads

---

## Definition of Done for Phase 2:
- [ ] All core statistics APIs functional and tested
- [ ] Response times meet performance requirements
- [ ] Error handling consistent across endpoints
- [ ] API documentation complete with examples
- [ ] Database optimized with proper indexes
- [ ] Caching implemented for expensive operations
- [ ] Artist and album detail pages return comprehensive data
- [ ] Chart data APIs return Chart.js-compatible format
- [ ] All time period filtering working correctly
- [ ] Custom date range filtering functional

## Integration Notes for Phase 3:
- Chart data endpoints are designed for Chart.js integration
- Artist/album detail APIs include all data needed for drill-down pages
- Time period filtering is consistent across all endpoints
- API responses are structured for easy frontend consumption
- Performance optimization enables smooth user experience

## Testing Recommendations:
- Test with full 150k scrobble dataset for performance validation
- Verify time period calculations with known data
- Test edge cases: no scrobbles, single scrobble, date boundaries
- Load test popular endpoints (recent tracks, top artists)
- Validate chart data accuracy against raw database queries