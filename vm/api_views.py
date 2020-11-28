from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from vm.models import Vm, VmTemplate, AWXTemplate
from vm.serializers import VmSerializer, VmTemplateSerializer, AWXTemplateSerializer
from vm.jobs import update_vm_job, delete_vm_job
from ipam.models import Network, Environment

from netaddr import *

class VmTemplateViewSet(viewsets.ModelViewSet):
    queryset = VmTemplate.objects.all()
    serializer_class = VmTemplateSerializer

class AWXTemplateViewSet(viewsets.ModelViewSet):
    queryset = AWXTemplate.objects.all()
    serializer_class = AWXTemplateSerializer

class VmViewSet(viewsets.ModelViewSet):
    queryset = Vm.objects.all()
    serializer_class = VmSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        environment = Environment.objects.get(pk=data['environment'])
        network = Network.objects.get(pk=data['network'])
        vm_template = VmTemplate.objects.get(pk=data['vm_template'])

        vm = Vm()
        vm.name = data['name']
        vm.state = {}
        vm.environment = environment
        vm.network = network
        vm.template = vm_template

        ipv4 = IPNetwork(network.get_next_ip()['ipv4'])
        ipv6 = IPNetwork(network.get_next_ip()['ipv6'])

        vm.config = {
            "name": vm.name,
            "role": 1,
            "hw": {
                "memory": data['memory'],
                "cpu_cores": data['cpu_cores'],
                "os_disk": data['os_disk'],
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
                "domain": environment.config['domain'],
                "firewall": True
            }
        }

        vm.config["awx_templates"] = {
            "ipa_install": {"id": 10, "name": "Install IPAClient", "trigger": {"after_state": ["netbox", "proxmox", "awx", "freeipa", "powerdns"]}},
            #"docker_test": {"id": 12, "name": "Docker Test", "trigger": {"after_state": ["netbox", "proxmox", "awx", "freeipa", "powerdns"]}}
        }

        vm.save()
        vm.update_netbox()
        update_vm_job.delay(vm.pk)
        return Response({'id': vm.pk, 'status': 'created'}, status=201)

    def destroy(self, request, *args, **kwargs):
        vm = self.get_object()
        delete_vm_job.delay(vm.pk)
        return Response(status=204)
