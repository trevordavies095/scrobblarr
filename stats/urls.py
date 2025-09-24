from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'stats', views.StatsViewSet, basename='stats')

app_name = 'stats'

urlpatterns = [
    path('', include(router.urls)),
]