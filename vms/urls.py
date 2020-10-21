from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='vms'),
    path('new', views.create, name='new_vm'),
    path('<int:id>', views.show, name='show_vm'),
    path('<int:id>/delete', views.delete, name='delete_vm'),
    path('<int:id>/update', views.update_state, name='update_vm'),
    path('<int:id>/template/<str:template_name>/run', views.run_awx_template, name='run_awx_template'),
]
