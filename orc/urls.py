from django.contrib import admin
from django.urls import include, path

from rest_framework import routers, serializers, viewsets
from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token, verify_jwt_token

from vm.api_views import VmViewSet
from ipam.api_views import EnvironmentViewSet, NetworkViewSet

router = routers.DefaultRouter()
router.register(r'vm', VmViewSet)
router.register(r'environment', EnvironmentViewSet)
router.register(r'network', NetworkViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api-token-auth/', obtain_jwt_token),
    path('api-token-refresh/', refresh_jwt_token),
    path('api-token-verify/', verify_jwt_token)
]

# Misc
urlpatterns += [
    path('admin/', admin.site.urls),
    path('django-rq/', include('django_rq.urls')),
]
