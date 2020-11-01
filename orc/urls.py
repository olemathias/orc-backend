from django.contrib import admin
from django.urls import include, path

from rest_framework import routers, serializers, viewsets
from orc.jwt_token import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from vm.api_views import VmViewSet
from ipam.api_views import EnvironmentViewSet, NetworkViewSet

router = routers.DefaultRouter()
router.register(r'vm', VmViewSet)
router.register(r'environment', EnvironmentViewSet)
router.register(r'network', NetworkViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api-token-auth/', TokenObtainPairView.as_view()),
    path('api-token-refresh/', TokenRefreshView.as_view()),
    path('api-token-verify/', TokenVerifyView.as_view())
]

# Misc
urlpatterns += [
    path('admin/', admin.site.urls),
    path('django-rq/', include('django_rq.urls')),
]
