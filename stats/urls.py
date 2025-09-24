from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'stats', views.StatsViewSet, basename='stats')

app_name = 'stats'

urlpatterns = [
    path('', include(router.urls)),
    # Story 9: Direct recent-tracks endpoint
    path('recent-tracks/', views.StatsViewSet.as_view({'get': 'recent_tracks'}), name='recent-tracks'),
    # Individual resource endpoints
    path('artists/<int:pk>/', views.StatsViewSet.as_view({'get': 'artists'}), name='artist-detail'),
    path('albums/<int:pk>/', views.StatsViewSet.as_view({'get': 'albums'}), name='album-detail'),
    path('tracks/<int:pk>/', views.StatsViewSet.as_view({'get': 'tracks'}), name='track-detail'),
]