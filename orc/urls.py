from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from orc.access import views as access
from orc.base import views as base

router = routers.DefaultRouter()

# Access
router.register(r'access/users', access.UserViewSet)
router.register(r'access/groups', access.GroupViewSet)

# Base
router.register(r'platform', base.PlatformViewSet, basename = "platform")
router.register(r'network', base.NetworkViewSet, basename = "network")
router.register(r'instance', base.InstanceViewSet, basename = "instance")

urlpatterns = [
    path('api/', include(router.urls)),
    path('admin/', admin.site.urls),
    path('django-rq/', include('django_rq.urls'))
]
