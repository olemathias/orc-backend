from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ipam.models import Environment, Network

class EnvironmentSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Environment
        fields = ['id', 'name', 'config', 'state', 'created', 'updated']

class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer

class NetworkSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Network
        fields = ['id', 'environment', 'environment_id', 'name', 'description', 'prefixes4', 'prefixes6', 'vid', 'config', 'state', 'created', 'updated']

class NetworkViewSet(viewsets.ModelViewSet):
    queryset = Network.objects.all()
    serializer_class = NetworkSerializer

    @action(detail=True)
    def get_next_ip(self, request, pk):
        network = Network.objects.get(pk=pk)
        return Response(network.get_next_ip())
