from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import render


class StatsViewSet(viewsets.ViewSet):
    """
    Basic stats API viewset - placeholder for future implementation
    """

    def list(self, request):
        return Response({"message": "Stats API - Coming soon"})

    @action(detail=False)
    def recent_tracks(self, request):
        return Response({"recent_tracks": []})

    @action(detail=False)
    def top_artists(self, request):
        return Response({"top_artists": []})

    @action(detail=False)
    def top_albums(self, request):
        return Response({"top_albums": []})

    @action(detail=False)
    def top_tracks(self, request):
        return Response({"top_tracks": []})