# Generated for Story 18: API Performance Optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0001_initial'),
    ]

    operations = [
        # Critical composite indexes for time-filtered queries (Story 18)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_timestamp_track ON scrobbles (timestamp, track_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_timestamp_track;"
        ),

        # Chart data aggregation indexes - use expression-based indexing
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_date_timestamp ON scrobbles (DATE(timestamp), timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_date_timestamp;"
        ),

        # Top lists optimization indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_tracks_artist_album ON tracks (artist_id, album_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_tracks_artist_album;"
        ),

        # Time range filtering optimization for descending order (recent tracks)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_timestamp_desc ON scrobbles (timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_timestamp_desc;"
        ),

        # Artist statistics aggregation - simplified without subquery
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_tracks_artist_id ON tracks (artist_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_tracks_artist_id;"
        ),

        # Album statistics aggregation - partial index for non-null albums
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_tracks_album_notnull ON tracks (album_id) WHERE album_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_tracks_album_notnull;"
        ),

        # Recent tracks optimization - covering index
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_timestamp_track_recent ON scrobbles (timestamp DESC, track_id, id);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_timestamp_track_recent;"
        ),

        # Chart data time-based aggregations
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_year_month ON scrobbles (strftime('%Y-%m', timestamp), timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_year_month;"
        ),

        # Weekly aggregations for different chart granularities
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_week ON scrobbles (strftime('%Y-%W', timestamp), timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_week;"
        ),

        # Daily aggregations for fine-grained charts
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_day ON scrobbles (strftime('%Y-%m-%d', timestamp), timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_day;"
        ),

        # Covering index for summary statistics
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_covering_summary ON scrobbles (timestamp, track_id, id);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_covering_summary;"
        ),

        # Multi-column index for joins between scrobbles and tracks
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_track_timestamp ON scrobbles (track_id, timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_track_timestamp;"
        ),

        # Index for track-album-artist joins (covers most common query patterns)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_tracks_full_relation ON tracks (artist_id, album_id, id);",
            reverse_sql="DROP INDEX IF EXISTS idx_tracks_full_relation;"
        ),

        # Additional composite index for better query performance
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_scrobbles_id_timestamp ON scrobbles (id, timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_scrobbles_id_timestamp;"
        ),
    ]