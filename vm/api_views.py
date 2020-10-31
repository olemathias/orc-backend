from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from vm.models import Vm
from vm.jobs import update_vm_job, delete_vm_job
from ipam.models import Network, Environment

from netaddr import *

# Serializers define the API representation.
class VmSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Vm
        fields = ['id', 'environment', 'environment_id', 'name', 'config', 'state', 'network', 'network_id', 'created', 'updated']

class VmViewSet(viewsets.ModelViewSet):
    queryset = Vm.objects.all()
    serializer_class = VmSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        environment = Environment.objects.get(pk=data['environment'])
        network = Network.objects.get(pk=data['network'])

        vm = Vm()
        vm.name = data['name']
        vm.state = {}
        vm.environment = environment
        vm.network = network

        ipv4 = IPNetwork(network.get_next_ip()['ipv4'])
        ipv6 = IPNetwork(network.get_next_ip()['ipv6'])

        vm.config = {
            "name": vm.name,
            "os_template": data['os_template'],
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
            "docker_test": {"id": 12, "name": "Docker Test", "trigger": {"after_state": ["netbox", "proxmox", "awx", "freeipa", "powerdns"]}}
        }

        vm.save()
        vm.update_netbox()
        update_vm_job.delay(vm.pk)
        return Response(status=201)

    def destroy(self, request, *args, **kwargs):
        vm = self.get_object()
        delete_vm_job.delay(vm.pk)
        return Response(status=204)
