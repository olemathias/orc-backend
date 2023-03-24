from rest_framework.response import Response
from orc.base.models import Platform, Network, Instance, InstanceTemplate
from orc.base.serializers import PlatformSerializer, NetworkSerializer, InstanceSerializer, InstanceCreateSerializer
from cerberus import Validator
from netaddr import IPNetwork
from orc.base.providers.netbox import create_vm as netbox_create_vm

from orc.base.jobs import create_instance_job, delete_instance_job

from orc.base.viewset import OrcViewSet


class PlatformViewSet(OrcViewSet):
    """
    PlatformViewSet
    """
    queryset = Platform.objects.all()
    serializer_class = PlatformSerializer
    allow_filters = ['id', 'name']


class NetworkViewSet(OrcViewSet):
    """
    NetworkViewSet
    """
    queryset = Network.objects.all()
    serializer_class = NetworkSerializer
    allow_filters = ['id', 'name', 'platform']


class InstanceViewSet(OrcViewSet):
    """
    InstanceViewSet
    """
    queryset = Instance.objects.all()
    serializer_class = InstanceSerializer
    allow_filters = ['id', 'name']

    def get_serializer_class(self):
        if (self.action == "create"):
            return InstanceCreateSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        data = request.data
        print(data)
        try:
            platform = Platform.objects.get(pk=data['platform'])
        except Exception:
            return Response(
                {'status': 'failed', 'errors': 'Platform not found'}, status=400)

        schema = {
            'name': {'type': 'string', 'required': True},
            'platform': {
                'type':
                    'string', 'required': True,
                    'allowed': list(Platform.objects.all().values_list('id', flat=True))
            },
            'network': {
                'type':
                    'string', 'required': True,
                    'allowed': list(Network.objects.filter(platform=data['platform']).values_list('id', flat=True))
            },
            'template': {
                'type':
                    'string', 'required': True,
                    'allowed': list(InstanceTemplate.objects.filter(platform=data['platform']).values_list('id', flat=True))
            },
            'memory': {
                'type': 'integer',
                'required': True,
                'min': 1,
                'max': 48,
                'coerce': int,
            },
            'cpu_cores': {
                'type': 'integer',
                'required': True,
                'min': 1,
                'max': 12,
                'coerce': int,
            },
            'os_disk': {
                'type': 'integer',
                'required': True,
                'min': 16,
                'max': 512,
                'coerce': int,
            },
            'userdata': {'type': 'list', 'required': False},
            'tags': {'type': 'list', 'required': False},
            'csrfmiddlewaretoken': {'type': 'string', 'required': False},
        }

        v = Validator(schema)
        if v.validate(data) is not True:
            print({'status': 'failed', 'errors': v.errors})
            return Response(
                {'status': 'failed', 'errors': v.errors}, status=400)

        network = Network.objects.get(pk=data['network'])
        template = InstanceTemplate.objects.get(pk=data['template'])

        instance = Instance()
        instance.name = data['name']
        instance.platform = platform
        instance.network = network
        instance.template = template
        instance.tags = data['tags']

        ipv4 = IPNetwork(network.get_next_ip()['ipv4'])
        ipv6 = IPNetwork(network.get_next_ip()['ipv6'])

        instance.config = {
            "memory": int(data['memory']),
            "cpu_cores": int(data['cpu_cores']),
            "disks": [{"name": "os-disk", "size": int(data['os_disk'])}],
            "interfaces": [{"name": "eth0", "network": network.id}],
            "userdata": data["userdata"] if "userdata" in data else None
        }

        if platform.ipam_provider_config['type'] == 'netbox':
            netbox_create_vm(instance, data, ipv4, ipv6)
        instance.save()

        create_instance_job.delay(instance.pk)

        return Response({'id': instance.pk, 'status': 'created'}, status=201)

    def destroy(self, request, pk=None):
        delete_instance_job.delay(pk)
        return Response({'id': pk, 'status': 'deleting', 'message': 'Scheduled for deletion'}, status=200)
