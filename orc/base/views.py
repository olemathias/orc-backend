from rest_framework import permissions
from rest_framework.response import Response
from orc.base.models import Platform, Network, Instance, InstanceImage
from orc.base.serializers import PlatformSerializer, NetworkSerializer, InstanceSerializer, InstanceCreateSerializer
from django.db.models import Q
from cerberus import Validator
from netaddr import IPNetwork

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
        if(self.action == "create"):
            return InstanceCreateSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        data = request.data
        try:
            platform = Platform.objects.get(pk=data['platform'])
        except Exception:
            return Response({'status': 'failed', 'errors': 'Platform not found'}, status=400)

        schema = {
            'name': {'type': 'string', 'required': True},
            'platform': {'type': 'string', 'required': True, 'allowed': list(Platform.objects.all().values_list('id', flat=True))},
            'network': {'type': 'string', 'required': True, 'allowed': list(Network.objects.filter(platform=data['platform']).values_list('id', flat=True))},
            'image': {'type': 'string', 'required': True, 'allowed': list(InstanceImage.objects.filter(platform=data['platform']).values_list('id', flat=True))},
            'memory': {'type': 'integer', 'required': True, 'min': 1, 'max': 48, 'coerce': int},
            'cpu_cores': {'type': 'integer', 'required': True, 'min': 1, 'max': 12, 'coerce': int},
            'os_disk': {'type': 'integer', 'required': True, 'min': 16, 'max': 512, 'coerce': int},
            'userdata': {'type': 'list', 'required': False},
            'tags': {'type': 'list', 'required': False},
            'csrfmiddlewaretoken': {'type': 'string', 'required': False},
        }

        v = Validator(schema)
        if v.validate(data) is not True:
            return Response({'status': 'failed', 'errors': v.errors}, status=400)

        network = Network.objects.get(pk=data['network'])
        image = InstanceImage.objects.get(pk=data['image'])

        instance = Instance()
        instance.name = data['name']
        instance.platform = platform
        instance.network = network
        instance.image = image
        instance.tags = data['tags']

        ipv4 = IPNetwork(network.get_next_ip()['ipv4'])
        ipv6 = IPNetwork(network.get_next_ip()['ipv6'])

        instance.config = {
            "memory": int(data['memory']),
            "cpu_cores": int(data['cpu_cores']),
            "disks": [{ "name": "os-disk", "size": int(data['os_disk']) }],
            "interfaces": [{"name": "eth0", "network": network.id}]
        }

        if platform.ipam_provider_config['type'] == 'netbox':
            ipam_instance_vm = None
            if instance.ipam_provider_state is None:
                instance.ipam_provider_state = {}
            if 'vm_id' not in instance.ipam_provider_state:
                ipam_instance_vm = instance.platform.ipam().virtualization.virtual_machines.create(
                    name=instance.name,
                    cluster=instance.platform.ipam_provider_config['cluster_id'],
                    vcpus=data['cpu_cores'],
                    memory=int(data['memory'])*1024,
                    disk=int(data['os_disk']),
                    status='active'
                )
                instance.ipam_provider_state = {"type": "netbox", "vm_id": ipam_instance_vm.id}

            if ipam_instance_vm is None:
                ipam_instance_vm = instance.platform.ipam().virtualization.virtual_machines.get(instance.ipam_provider_state['vm_id'])

            if instance.platform.ipam().virtualization.interfaces.get(virtual_machine_id=ipam_instance_vm.id, name="eth0") is None:
                ipam_instance_interface = instance.platform.ipam().virtualization.interfaces.create(
                    virtual_machine=ipam_instance_vm.id,
                    name='eth0'
                )
                ipam_instance_ipv4 = instance.platform.ipam().ipam.ip_addresses.create(
                    assigned_object_type="virtualization.vminterface",
                    assigned_object_id=ipam_instance_interface['id'],
                    address=str(ipv4),
                    status="active"
                )
                ipam_instance_ipv6 = instance.platform.ipam().ipam.ip_addresses.create(
                    assigned_object_type="virtualization.vminterface",
                    assigned_object_id=ipam_instance_interface['id'],
                    address=str(ipv6),
                    status="active"
                )
                ipam_instance_vm.primary_ip4 = ipam_instance_ipv4['id']
                ipam_instance_vm.primary_ip6 = ipam_instance_ipv6['id']
                ipam_instance_vm.save()

                if 'interface' not in instance.ipam_provider_state:
                    instance.ipam_provider_state['interface'] = []
                instance.ipam_provider_state['interface'].append({'id': ipam_instance_interface['id'], 'name': ipam_instance_interface['name']})

                if 'ip_addresses' not in instance.ipam_provider_state:
                    instance.ipam_provider_state['ip_addresses'] = []
                instance.ipam_provider_state['ip_addresses'].append({'id': ipam_instance_ipv4['id'], 'address': ipam_instance_ipv4['address'], 'interface_id': ipam_instance_ipv4['assigned_object_id']})
                instance.ipam_provider_state['ip_addresses'].append({'id': ipam_instance_ipv6['id'], 'address': ipam_instance_ipv6['address'], 'interface_id': ipam_instance_ipv6['assigned_object_id']})

                instance.ipam_provider_state['status'] = "provisioned"
        instance.save()

        return Response({'id': instance.pk, 'status': 'created'}, status=201)
