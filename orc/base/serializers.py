from orc.base.models import Platform, Network, Instance, InstanceImage
from rest_framework import serializers


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Network
        fields = '__all__'
        depth = 0


class InstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instance
        fields = '__all__'
        depth = 3


class InstanceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstanceImage
        fields = '__all__'
        depth = 3


class PlatformSerializer(serializers.ModelSerializer):
    networks = NetworkSerializer(read_only=True, many=True)
    instance_images = InstanceImageSerializer(read_only=True, many=True)

    class Meta:
        model = Platform
        fields = '__all__'
        depth = 1


class InstanceCreateSerializer(serializers.Serializer):
    platform = serializers.CharField()
    network = serializers.CharField()
    image = serializers.CharField()
    name = serializers.CharField()
    tags = serializers.ListField(
        child=serializers.DictField()
    )
    cpu_cores = serializers.IntegerField()
    memory = serializers.IntegerField()
    os_disk = serializers.IntegerField()