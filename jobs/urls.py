from django.urls import path

from . import views

urlpatterns = [
    path('<str:task>/<str:status>', views.jobs, name='jobs'),
    path('<int:id>', views.job, name='job'),
]
