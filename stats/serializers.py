from rest_framework import serializers
from music.models import Artist, Album, Track, Scrobble
from django.db.models import Count, Q
import logging

logger = logging.getLogger('stats.serializers')


class ArtistListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for artist lists with counts."""
    track_count = serializers.IntegerField(read_only=True)
    album_count = serializers.IntegerField(read_only=True)
    scrobble_count = serializers.IntegerField(read_only=True)
    last_scrobbled = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Artist
        fields = ['id', 'name', 'mbid', 'url', 'track_count', 'album_count', 'scrobble_count', 'last_scrobbled']


class AlbumListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for album lists with counts."""
    artist_name = serializers.CharField(source='artist.name', read_only=True)
    artist_id = serializers.IntegerField(source='artist.id', read_only=True)
    track_count = serializers.IntegerField(read_only=True)
    scrobble_count = serializers.IntegerField(read_only=True)
    last_scrobbled = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Album
        fields = ['id', 'name', 'mbid', 'url', 'artist_name', 'artist_id', 'track_count', 'scrobble_count', 'last_scrobbled']


class TopAlbumsSerializer(serializers.ModelSerializer):
    """
    Story 11 compliant serializer for top albums API.
    Returns album, artist, scrobble_count, mbid format.
    """
    album = serializers.CharField(source='name', read_only=True)
    artist = serializers.CharField(source='artist.name', read_only=True)
    scrobble_count = serializers.IntegerField(read_only=True)
    mbid = serializers.CharField(read_only=True)

    class Meta:
        model = Album
        fields = ['album', 'artist', 'scrobble_count', 'mbid']


class TopTracksSerializer(serializers.ModelSerializer):
    """
    Story 12 compliant serializer for top tracks API.
    Returns track, artist, album, scrobble_count, mbid format.
    """
    track = serializers.CharField(source='name', read_only=True)
    artist = serializers.CharField(source='artist.name', read_only=True)
    album = serializers.SerializerMethodField()
    scrobble_count = serializers.IntegerField(read_only=True)
    mbid = serializers.CharField(read_only=True)

    class Meta:
        model = Track
        fields = ['track', 'artist', 'album', 'scrobble_count', 'mbid']

    def get_album(self, obj):
        """Get album name, handling tracks with missing album information."""
        return obj.album.name if obj.album else None


class ScrobblesChartSerializer(serializers.Serializer):
    """
    Story 13 compliant serializer for scrobbles chart data API.
    Optimized for Chart.js consumption with time-series data.
    """
    period = serializers.CharField(read_only=True)
    scrobble_count = serializers.IntegerField(read_only=True)
    start_date = serializers.CharField(read_only=True)
    end_date = serializers.CharField(read_only=True)

    class Meta:
        fields = ['period', 'scrobble_count', 'start_date', 'end_date']


class TrackListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for track lists with counts."""
    artist_name = serializers.CharField(source='artist.name', read_only=True)
    artist_id = serializers.IntegerField(source='artist.id', read_only=True)
    album_name = serializers.CharField(source='album.name', read_only=True)
    album_id = serializers.IntegerField(source='album.id', read_only=True)
    scrobble_count = serializers.IntegerField(read_only=True)
    last_scrobbled = serializers.DateTimeField(read_only=True)
    duration_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = ['id', 'name', 'mbid', 'url', 'duration', 'duration_formatted',
                 'artist_name', 'artist_id', 'album_name', 'album_id', 'scrobble_count', 'last_scrobbled']

    def get_duration_formatted(self, obj):
        return obj.get_duration_formatted()


class ScrobbleListSerializer(serializers.ModelSerializer):
    """Serializer for scrobble lists with track details."""
    track_name = serializers.CharField(source='track.name', read_only=True)
    track_id = serializers.IntegerField(source='track.id', read_only=True)
    artist_name = serializers.CharField(source='track.artist.name', read_only=True)
    artist_id = serializers.IntegerField(source='track.artist.id', read_only=True)
    album_name = serializers.CharField(source='track.album.name', read_only=True)
    album_id = serializers.IntegerField(source='track.album.id', read_only=True)

    class Meta:
        model = Scrobble
        fields = ['id', 'timestamp', 'track_name', 'track_id', 'artist_name', 'artist_id',
                 'album_name', 'album_id', 'lastfm_reference_id']


class RecentTracksSerializer(serializers.ModelSerializer):
    """
    Story 9 compliant serializer for recent tracks API.
    Returns track, artist, album, timestamp format.
    """
    track = serializers.CharField(source='track.name', read_only=True)
    artist = serializers.CharField(source='track.artist.name', read_only=True)
    album = serializers.CharField(source='track.album.name', read_only=True)
    timestamp = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%SZ', read_only=True)

    class Meta:
        model = Scrobble
        fields = ['track', 'artist', 'album', 'timestamp']


class TrackDetailSerializer(serializers.ModelSerializer):
    """Detailed track serializer with nested artist/album."""
    artist = ArtistListSerializer(read_only=True)
    album = AlbumListSerializer(read_only=True)
    scrobble_count = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()
    recent_scrobbles = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = ['id', 'name', 'mbid', 'url', 'duration', 'duration_formatted',
                 'artist', 'album', 'scrobble_count', 'recent_scrobbles', 'created_at']

    def get_scrobble_count(self, obj):
        return obj.scrobbles.count()

    def get_duration_formatted(self, obj):
        return obj.get_duration_formatted()

    def get_recent_scrobbles(self, obj):
        recent = obj.scrobbles.all()[:10]
        return [{'timestamp': s.timestamp, 'id': s.id} for s in recent]


class AlbumDetailSerializer(serializers.ModelSerializer):
    """Detailed album serializer with tracks."""
    artist = ArtistListSerializer(read_only=True)
    tracks = TrackListSerializer(many=True, read_only=True)
    track_count = serializers.SerializerMethodField()
    scrobble_count = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = ['id', 'name', 'mbid', 'url', 'artist', 'tracks', 'track_count', 'scrobble_count', 'created_at']

    def get_track_count(self, obj):
        return obj.tracks.count()

    def get_scrobble_count(self, obj):
        return obj.get_scrobble_count()


class ArtistDetailSerializer(serializers.ModelSerializer):
    """Detailed artist serializer with albums and top tracks."""
    albums = AlbumListSerializer(many=True, read_only=True)
    top_tracks = serializers.SerializerMethodField()
    track_count = serializers.SerializerMethodField()
    album_count = serializers.SerializerMethodField()
    scrobble_count = serializers.SerializerMethodField()

    class Meta:
        model = Artist
        fields = ['id', 'name', 'mbid', 'url', 'albums', 'top_tracks', 'track_count',
                 'album_count', 'scrobble_count', 'created_at']

    def get_top_tracks(self, obj):
        top_tracks = obj.tracks.annotate(
            scrobble_count=Count('scrobbles')
        ).order_by('-scrobble_count')[:10]
        return TrackListSerializer(top_tracks, many=True).data

    def get_track_count(self, obj):
        return obj.tracks.count()

    def get_album_count(self, obj):
        return obj.albums.count()

    def get_scrobble_count(self, obj):
        return obj.get_scrobble_count()


class ArtistStory14Serializer(serializers.Serializer):
    """
    Story 14 compliant serializer for artist detail API.
    Returns nested structure with artist info, top albums, top tracks, and chart data.
    """
    artist = serializers.SerializerMethodField()
    top_albums = serializers.SerializerMethodField()
    top_tracks = serializers.SerializerMethodField()
    chart_data = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        # Extract context parameters
        self.time_filter = kwargs.pop('time_filter', None)
        self.period_display = kwargs.pop('period_display', 'all')
        self.limit = kwargs.pop('limit', 10)
        super().__init__(*args, **kwargs)

    def get_artist(self, obj):
        """Get basic artist information with scrobble stats."""
        # Get first and last scrobble dates
        scrobble_qs = Scrobble.objects.filter(track__artist=obj)
        if self.time_filter:
            if isinstance(self.time_filter, tuple):
                # Custom date range: (from_date, to_date)
                from_date, to_date = self.time_filter
                if from_date:
                    scrobble_qs = scrobble_qs.filter(timestamp__gte=from_date)
                if to_date:
                    scrobble_qs = scrobble_qs.filter(timestamp__lte=to_date)
            else:
                # Period-based filtering: single datetime
                scrobble_qs = scrobble_qs.filter(timestamp__gte=self.time_filter)

        first_scrobble = scrobble_qs.order_by('timestamp').first()
        last_scrobble = scrobble_qs.order_by('-timestamp').first()

        return {
            'name': obj.name,
            'mbid': obj.mbid,
            'total_scrobbles': scrobble_qs.count(),
            'first_scrobble': first_scrobble.timestamp.isoformat() + 'Z' if first_scrobble else None,
            'last_scrobble': last_scrobble.timestamp.isoformat() + 'Z' if last_scrobble else None
        }

    def get_top_albums(self, obj):
        """Get top albums by this artist with scrobble counts."""
        albums_qs = Album.objects.filter(artist=obj)

        # Apply time filtering to scrobbles
        scrobble_filter = Q()
        if self.time_filter:
            if isinstance(self.time_filter, tuple):
                # Custom date range: (from_date, to_date)
                from_date, to_date = self.time_filter
                if from_date:
                    scrobble_filter &= Q(tracks__scrobbles__timestamp__gte=from_date)
                if to_date:
                    scrobble_filter &= Q(tracks__scrobbles__timestamp__lte=to_date)
            else:
                # Period-based filtering: single datetime
                scrobble_filter = Q(tracks__scrobbles__timestamp__gte=self.time_filter)

        albums_with_counts = albums_qs.annotate(
            scrobble_count=Count('tracks__scrobbles', filter=scrobble_filter)
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')[:self.limit]

        return [
            {
                'album': album.name,
                'scrobble_count': album.scrobble_count
            }
            for album in albums_with_counts
        ]

    def get_top_tracks(self, obj):
        """Get top tracks by this artist with scrobble counts."""
        tracks_qs = Track.objects.filter(artist=obj)

        # Apply time filtering to scrobbles
        scrobble_filter = Q()
        if self.time_filter:
            if isinstance(self.time_filter, tuple):
                # Custom date range: (from_date, to_date)
                from_date, to_date = self.time_filter
                if from_date:
                    scrobble_filter &= Q(scrobbles__timestamp__gte=from_date)
                if to_date:
                    scrobble_filter &= Q(scrobbles__timestamp__lte=to_date)
            else:
                # Period-based filtering: single datetime
                scrobble_filter = Q(scrobbles__timestamp__gte=self.time_filter)

        tracks_with_counts = tracks_qs.annotate(
            scrobble_count=Count('scrobbles', filter=scrobble_filter)
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')[:self.limit]

        return [
            {
                'track': track.name,
                'album': track.album.name if track.album else None,
                'scrobble_count': track.scrobble_count
            }
            for track in tracks_with_counts
        ]

    def get_chart_data(self, obj):
        """Get chart data for this artist using existing chart infrastructure."""
        # This will be populated by the view with chart data
        return self.context.get('chart_data', {})