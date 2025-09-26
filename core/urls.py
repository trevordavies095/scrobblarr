from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('recent/', views.recent_tracks, name='recent'),
    path('top-artists/', views.top_artists, name='top-artists'),
    path('top-albums/', views.top_albums, name='top-albums'),
    path('top-tracks/', views.top_tracks, name='top-tracks'),
    path('charts/', views.charts, name='charts'),
    path('artists/<int:pk>/', views.artist_detail, name='artist-detail'),
    path('health/', views.health_check, name='health_check'),
    path('health/readiness/', views.readiness_check, name='readiness_check'),
    path('health/liveness/', views.liveness_check, name='liveness_check'),
]