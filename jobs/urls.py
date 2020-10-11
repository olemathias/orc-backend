from django.urls import path

from . import views

urlpatterns = [
    path('', views.get_jobs, name='get_jobs'),
]
