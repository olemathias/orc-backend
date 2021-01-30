from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ipam.models import Platform, Network
from ipam.serializers import PlatformSerializer, NetworkSerializer


class PlatformViewSet(viewsets.ModelViewSet):
    queryset = Platform.objects.all()
    serializer_class = PlatformSerializer

    @action(detail=True)
    def get_ipa_hostgroups(self, request, pk):
        platform = Platform.objects.get(pk=pk)
        groups = []
        for group in platform.freeipa().hostgroup_find()['result']:
            groups.append(group['cn'][0])
        return Response(groups)

class NetworkViewSet(viewsets.ModelViewSet):
    queryset = Network.objects.all()
    serializer_class = NetworkSerializer

    @action(detail=True)
    def get_next_ip(self, request, pk):
        network = Network.objects.get(pk=pk)
        return Response(network.get_next_ip())
