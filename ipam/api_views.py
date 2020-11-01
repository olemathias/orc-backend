from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ipam.models import Environment, Network
from ipam.serializers import EnvironmentSerializer, NetworkSerializer


class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer


class NetworkViewSet(viewsets.ModelViewSet):
    queryset = Network.objects.all()
    serializer_class = NetworkSerializer

    @action(detail=True)
    def get_next_ip(self, request, pk):
        network = Network.objects.get(pk=pk)
        return Response(network.get_next_ip())