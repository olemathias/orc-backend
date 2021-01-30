from rest_framework import serializers

from ipam.models import Platform, Network

class PlatformSerializer(serializers.HyperlinkedModelSerializer):
    config = serializers.JSONField(source='stripped_config')

    class Meta:
        model = Platform
        fields = ['id', 'name', 'config', 'state', 'created', 'updated']

class PlatformSerializerSummary(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Platform
        fields = ['id', 'name']

class NetworkSerializer(serializers.HyperlinkedModelSerializer):
    platform = PlatformSerializerSummary(read_only=True)

    class Meta:
        model = Network
        fields = ['id', 'platform', 'name', 'description', 'prefixes4', 'prefixes6', 'vid', 'config', 'state', 'created', 'updated']

class NetworkSerializerSummary(serializers.HyperlinkedModelSerializer):
    platform = PlatformSerializerSummary(read_only=True)

    class Meta:
        model = Network
        fields = ['id', 'platform', 'name', 'description', 'prefixes4', 'prefixes6', 'vid']
