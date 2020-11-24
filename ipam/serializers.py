from rest_framework import serializers

from ipam.models import Environment, Network

class EnvironmentSerializer(serializers.HyperlinkedModelSerializer):
    config = serializers.JSONField(source='stripped_config')

    class Meta:
        model = Environment
        fields = ['id', 'name', 'config', 'state', 'created', 'updated']

class EnvironmentSerializerSummary(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Environment
        fields = ['id', 'name']

class NetworkSerializer(serializers.HyperlinkedModelSerializer):
    environment = EnvironmentSerializerSummary(read_only=True)

    class Meta:
        model = Network
        fields = ['id', 'environment', 'name', 'description', 'prefixes4', 'prefixes6', 'vid', 'config', 'state', 'created', 'updated']

class NetworkSerializerSummary(serializers.HyperlinkedModelSerializer):
    environment = EnvironmentSerializerSummary(read_only=True)

    class Meta:
        model = Network
        fields = ['id', 'environment', 'name', 'description', 'prefixes4', 'prefixes6', 'vid']
