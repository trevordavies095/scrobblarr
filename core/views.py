from django.shortcuts import render
from django.http import HttpResponse


def index(request):
    """
    Home page view for Scrobblarr.
    """
    return HttpResponse("Welcome to Scrobblarr - Your Last.fm Analytics Dashboard")