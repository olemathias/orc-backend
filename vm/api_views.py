from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from vm.models import Vm, VmTemplate
from vm.serializers import VmSerializer, VmTemplateSerializer
from vm.jobs import update_vm_job, delete_vm_job
from ipam.models import Network, Platform

from netaddr import *
from cerberus import Validator

class VmTemplateViewSet(viewsets.ModelViewSet):
    queryset = VmTemplate.objects.all()
    serializer_class = VmTemplateSerializer

class VmViewSet(viewsets.ModelViewSet):
    queryset = Vm.objects.all()
    serializer_class = VmSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        try:
            platform = Platform.objects.get(pk=data['platform'])
        except Exception:
            return Response({'status': 'failed', 'errors': 'Platform not found'}, status=400)

        # TODO Support max values (mem, cpu, disk) overrides in platform
        schema = {
            'name': {'type': 'string', 'required': True, 'minlength': 3, 'maxlength': 63, 'regex': '^(?!-)[a-z\d-]{1,63}(?<!-)$'},
            'platform': {'type': 'integer', 'required': True, 'allowed': list(Platform.objects.all().values_list('id', flat=True))},
            'network': {'type': 'integer', 'required': True, 'allowed': list(Network.objects.filter(platform=data['platform']).values_list('id', flat=True))},
            'vm_template': {'type': 'integer', 'required': True, 'allowed': list(VmTemplate.objects.filter(platform=data['platform']).values_list('id', flat=True))},
            'memory': {'type': 'integer', 'required': True, 'min': 1, 'max': 48},
            'cpu_cores': {'type': 'integer', 'required': True, 'min': 1, 'max': 12},
            'os_disk': {'type': 'integer', 'required': True, 'min': 16, 'max': 512},
            'userdata': {'type': 'list', 'required': False},
        }
        v = Validator(schema)
        if v.validate(data) is not True:
            return Response({'status': 'failed', 'errors': v.errors}, status=400)

        network = Network.objects.get(pk=data['network'])
        vm_template = VmTemplate.objects.get(pk=data['vm_template'])

        vm = Vm()
        vm.name = data['name'].lower()
        vm.state = {}
        vm.platform = platform
        vm.network = network
        vm.template = vm_template

        ipv4 = IPNetwork(network.get_next_ip()['ipv4'])
        ipv6 = IPNetwork(network.get_next_ip()['ipv6'])

        vm.config = {
            "name": vm.name,
            "role": 1,
            "hw": {
                "memory": int(data['memory']),
                "cpu_cores": int(data['cpu_cores']),
                "os_disk": int(data['os_disk']),
            },
            "net": {
                "vlan_id": network.vid,
                "ipv4": {
                    "ip": str(ipv4.ip),
                    "prefixlen": ipv4.prefixlen,
                    "gw": str(ipv4[1])
                },
                "ipv6": {
                    "ip": str(ipv6.ip),
                    "prefixlen": ipv6.prefixlen,
                    "gw": str(ipv6[1])
                },
                "domain": platform.config['domain'],
                "firewall": True
            }
        }

        if 'userdata' in data and data['userdata'] is not None:
            vm.config['userdata'] = data['userdata']

        vm.save()

        vm.config["awx_templates"] = {
            "ipa_install": {"id": 10, "name": "Install IPAClient", "trigger": {"after_state": ["netbox", "proxmox", "awx", "freeipa", "powerdns"]}},
            #"docker_test": {"id": 12, "name": "Docker Test", "trigger": {"after_state": ["netbox", "proxmox", "awx", "freeipa", "powerdns"]}}
        }

        vm.update_netbox()
        update_vm_job.delay(vm.pk)
        return Response({'id': vm.pk, 'status': 'created'}, status=201)

    def destroy(self, request, *args, **kwargs):
        vm = self.get_object()
        delete_vm_job.delay(vm.pk)
        return Response(status=204)
