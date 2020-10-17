from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('new', views.create, name='new'),
    path('<int:id>', views.show, name='show'),
]
