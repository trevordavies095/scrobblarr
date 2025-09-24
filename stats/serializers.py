from rest_framework import serializers
from music.models import Artist, Album, Track, Scrobble
from django.db.models import Count, Max
from django.utils import timezone


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