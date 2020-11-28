from rest_framework import serializers
from vm.models import Vm, VmTemplate, AWXTemplate

from ipam.serializers import EnvironmentSerializerSummary, NetworkSerializerSummary

class VmSerializer(serializers.HyperlinkedModelSerializer):
    environment = EnvironmentSerializerSummary(read_only=True)
    network = NetworkSerializerSummary(read_only=True)
    class Meta:
        model = Vm
        fields = ['id', 'environment', 'name', 'fqdn', 'config', 'state', 'network', 'created', 'updated']

class VmTemplateSerializer(serializers.HyperlinkedModelSerializer):
    environment = EnvironmentSerializerSummary(read_only=True)
    class Meta:
        model = VmTemplate
        fields = ['id', 'environment', 'name', 'config', 'created', 'updated']

class AWXTemplateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = AWXTemplate
        fields = ['id', 'name', 'config', 'created', 'updated']
