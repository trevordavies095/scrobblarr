from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('health/', views.health_check, name='health_check'),
    path('health/readiness/', views.readiness_check, name='readiness_check'),
    path('health/liveness/', views.liveness_check, name='liveness_check'),
]