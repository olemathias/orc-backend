from rest_framework import serializers
from vm.models import Vm, VmTemplate

from ipam.serializers import PlatformSerializerSummary, NetworkSerializerSummary

class VmSerializer(serializers.HyperlinkedModelSerializer):
    platform = PlatformSerializerSummary(read_only=True)
    network = NetworkSerializerSummary(read_only=True)
    class Meta:
        model = Vm
        fields = ['id', 'platform', 'name', 'fqdn', 'status', 'config', 'state', 'network', 'created', 'updated']

class VmTemplateSerializer(serializers.HyperlinkedModelSerializer):
    platform = PlatformSerializerSummary(read_only=True)
    class Meta:
        model = VmTemplate
        fields = ['id', 'platform', 'name', 'config', 'created', 'updated']
