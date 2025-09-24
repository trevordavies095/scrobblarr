import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q, Max
from django.utils import timezone
from django.http import Http404
from datetime import timedelta
from music.models import Artist, Album, Track, Scrobble
from core.exceptions import APIError, DataValidationError
from .serializers import (
    ArtistListSerializer, ArtistDetailSerializer,
    AlbumListSerializer, AlbumDetailSerializer,
    TrackListSerializer, TrackDetailSerializer,
    ScrobbleListSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class StatsViewSet(viewsets.ViewSet):
    """
    Stats API viewset for music analytics
    """
    pagination_class = StandardResultsSetPagination

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('stats.api')

    def get_time_filter(self, request):
        """Get time filter based on period parameter."""
        period = request.query_params.get('period', '30d')
        now = timezone.now()

        time_filters = {
            '7d': now - timedelta(days=7),
            '30d': now - timedelta(days=30),
            '90d': now - timedelta(days=90),
            '365d': now - timedelta(days=365),
            'all': None
        }

        if period not in time_filters:
            self.logger.warning(
                f"Invalid period parameter provided: {period}",
                extra={
                    'period': period,
                    'valid_periods': list(time_filters.keys()),
                    'request_path': request.path
                }
            )
            # Return default instead of raising error
            period = '30d'

        return time_filters.get(period, time_filters['30d'])

    def list(self, request):
        """API overview with available endpoints."""
        return Response({
            "message": "Scrobblarr Music Analytics API",
            "endpoints": {
                "recent_tracks": "/api/recent-tracks/",
                "top_artists": "/api/top-artists/?period=30d",
                "top_albums": "/api/top-albums/?period=30d",
                "top_tracks": "/api/top-tracks/?period=30d",
                "artists": "/api/artists/{id}/",
                "albums": "/api/albums/{id}/",
                "tracks": "/api/tracks/{id}/"
            },
            "time_periods": ["7d", "30d", "90d", "365d", "all"]
        })

    @action(detail=False)
    def recent_tracks(self, request):
        """Get recent listening activity."""
        scrobbles = Scrobble.objects.select_related(
            'track', 'track__artist', 'track__album'
        ).order_by('-timestamp')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(scrobbles, request)

        if page is not None:
            serializer = ScrobbleListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ScrobbleListSerializer(scrobbles, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def top_artists(self, request):
        """Get top artists by play count with time filtering."""
        time_filter = self.get_time_filter(request)

        artists = Artist.objects.annotate(
            scrobble_count=Count(
                'tracks__scrobbles',
                filter=Q(tracks__scrobbles__timestamp__gte=time_filter) if time_filter else Q()
            ),
            track_count=Count('tracks', distinct=True),
            album_count=Count('albums', distinct=True),
            last_scrobbled=Max(
                'tracks__scrobbles__timestamp',
                filter=Q(tracks__scrobbles__timestamp__gte=time_filter) if time_filter else Q()
            )
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(artists, request)

        if page is not None:
            serializer = ArtistListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ArtistListSerializer(artists, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def top_albums(self, request):
        """Get top albums by play count with time filtering."""
        time_filter = self.get_time_filter(request)

        albums = Album.objects.select_related('artist').annotate(
            scrobble_count=Count(
                'tracks__scrobbles',
                filter=Q(tracks__scrobbles__timestamp__gte=time_filter) if time_filter else Q()
            ),
            track_count=Count('tracks', distinct=True),
            last_scrobbled=Max(
                'tracks__scrobbles__timestamp',
                filter=Q(tracks__scrobbles__timestamp__gte=time_filter) if time_filter else Q()
            )
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(albums, request)

        if page is not None:
            serializer = AlbumListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = AlbumListSerializer(albums, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def top_tracks(self, request):
        """Get top tracks by play count with time filtering."""
        time_filter = self.get_time_filter(request)

        tracks = Track.objects.select_related('artist', 'album').annotate(
            scrobble_count=Count(
                'scrobbles',
                filter=Q(scrobbles__timestamp__gte=time_filter) if time_filter else Q()
            ),
            last_scrobbled=Max(
                'scrobbles__timestamp',
                filter=Q(scrobbles__timestamp__gte=time_filter) if time_filter else Q()
            )
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(tracks, request)

        if page is not None:
            serializer = TrackListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = TrackListSerializer(tracks, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def artists(self, request, pk=None):
        """Get artist detail with statistics."""
        try:
            artist = get_object_or_404(Artist.objects.prefetch_related('albums', 'tracks'), pk=pk)
            self.logger.info(
                f"Artist detail requested",
                extra={'artist_id': pk, 'artist_name': artist.name}
            )
            serializer = ArtistDetailSerializer(artist)
            return Response(serializer.data)
        except Http404:
            self.logger.warning(f"Artist not found", extra={'artist_id': pk})
            raise APIError(f"Artist with ID {pk} not found", status_code=404)
        except Exception as e:
            self.logger.error(
                f"Error retrieving artist detail",
                extra={'artist_id': pk, 'exception': str(e)},
                exc_info=True
            )
            raise APIError("Error retrieving artist data", status_code=500)

    @action(detail=True)
    def albums(self, request, pk=None):
        """Get album detail with track listings."""
        try:
            album = get_object_or_404(
                Album.objects.select_related('artist').prefetch_related('tracks'),
                pk=pk
            )
            self.logger.info(
                f"Album detail requested",
                extra={'album_id': pk, 'album_name': album.name, 'artist_name': album.artist.name}
            )
            serializer = AlbumDetailSerializer(album)
            return Response(serializer.data)
        except Http404:
            self.logger.warning(f"Album not found", extra={'album_id': pk})
            raise APIError(f"Album with ID {pk} not found", status_code=404)
        except Exception as e:
            self.logger.error(
                f"Error retrieving album detail",
                extra={'album_id': pk, 'exception': str(e)},
                exc_info=True
            )
            raise APIError("Error retrieving album data", status_code=500)

    @action(detail=True)
    def tracks(self, request, pk=None):
        """Get track detail with scrobble history."""
        try:
            track = get_object_or_404(
                Track.objects.select_related('artist', 'album').prefetch_related('scrobbles'),
                pk=pk
            )
            self.logger.info(
                f"Track detail requested",
                extra={
                    'track_id': pk,
                    'track_name': track.name,
                    'artist_name': track.artist.name,
                    'album_name': track.album.name if track.album else None
                }
            )
            serializer = TrackDetailSerializer(track)
            return Response(serializer.data)
        except Http404:
            self.logger.warning(f"Track not found", extra={'track_id': pk})
            raise APIError(f"Track with ID {pk} not found", status_code=404)
        except Exception as e:
            self.logger.error(
                f"Error retrieving track detail",
                extra={'track_id': pk, 'exception': str(e)},
                exc_info=True
            )
            raise APIError("Error retrieving track data", status_code=500)