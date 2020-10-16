from django.db import models
from django.conf import settings
from ipam.models import Network
from jobs.models import Job

import pynetbox
import proxmoxer

# Create your models here.
class HostCluster(models.Model):
    type = models.CharField(max_length=16)
    name = models.CharField(max_length=256)
    status = models.CharField(max_length=64)
    netbox_cluster_id = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    nb = pynetbox.api(
        settings.NETBOX_URL,
        token=settings.NETBOX_TOKEN
    )
    nb_cluster = None

    def get_site_id(self):
        self.fetch_from_netbox_cluster()
        return self.nb_cluster.site.id

    def fetch_from_netbox_cluster(self):
        if self.nb_cluster is None:
            self.nb_cluster = self.nb.virtualization.clusters.get(self.netbox_cluster_id)

    def __str__(self):
        return self.name

class HostClusterNode(models.Model):
    host_cluster = models.ForeignKey(HostCluster, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    url = models.CharField(max_length=256)
    status = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Vm(models.Model):
    host_cluster = models.ForeignKey(HostCluster, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    config = models.JSONField()
    state = models.JSONField()
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    nb = pynetbox.api(
        settings.NETBOX_URL,
        token=settings.NETBOX_TOKEN
    )
    def __str__(self):
        return self.name

    def refresh_state(self):
        self.update_netbox()
        self.update_powerdns()
        self.update_proxmox()
        self.update_freeipa()
        self.update_awx()
        self.update_monitoring()

    def update_netbox(self):
        vm = None
        if 'netbox' not in self.state:
            self.state['netbox'] = {}
            vm = self.nb.virtualization.virtual_machines.create(
                name=self.name,
                site=self.host_cluster.get_site_id(),
                cluster=self.host_cluster.netbox_cluster_id,
                role=self.config['role'],
                vcpus=self.config['hw']['cpu_cores'],
                memory=int(self.config['hw']['memory'])*1024,
                disk=int(self.config['hw']['os_disk']),
                status='active'
            )
            self.state['netbox']['id'] = vm.id
            self.save()

        if vm is None:
            vm = self.nb.virtualization.virtual_machines.get(self.state['netbox']['id'])

        if self.nb.virtualization.interfaces.get(virtual_machine_id=vm.id, name="eth0") is None:
            interface = self.nb.virtualization.interfaces.create(
                virtual_machine=vm.id,
                name='eth0'
            )
            ipv4 = self.nb.ipam.ip_addresses.create(
                assigned_object_type="virtualization.vminterface",
                assigned_object_id=interface['id'],
                address="{}/{}".format(self.config['config']['ipv4']['ip'], self.config['config']['ipv4']['prefixlen']),
                status="active"
             )
            ipv6 = self.nb.ipam.ip_addresses.create(
                assigned_object_type="virtualization.vminterface",
                assigned_object_id=interface['id'],
                address="{}/{}".format(self.config['config']['ipv6']['ip'], self.config['config']['ipv6']['prefixlen']),
                status="active"
            )
            vm.primary_ip4 = ipv4['id']
            vm.primary_ip6 = ipv6['id']
            vm.save()

            return self.state['netbox']

    def update_proxmox(self):
        proxmox = proxmoxer.ProxmoxAPI(settings.PROXMOX_URL, user=settings.PROXMOX_USERNAME, token_name=settings.PROXMOX_TOKEN_NAME, token_value=settings.PROXMOX_TOKEN_VALUE, verify_ssl=False)
        if 'proxmox' not in self.state:
            self.state['proxmox'] = {"id": None}
            self.save()
            job = Job(task="create_vm", status="new")
            job.description = "Create VM {} in {}".format(vm.name, vm.host_cluster)
            job.job = {**vm.config, **{"vm_id": vm.pk}}
            job.save()

        if 'vmid' in self.state['proxmox'] and self.state['proxmox']['vmid'] is not None:
            vm = None
            for node in proxmox.nodes.get():
                try:
                    vm = proxmox.nodes(node['node']).qemu(self.state['proxmox']['vmid'])
                    if vm is not None:
                        status = vm.status().current.get()
                        config = vm.config().get()
                        self.state['proxmox']['name'] = status['name']
                        self.state['proxmox']['status'] = status['status']
                        self.state['proxmox']['node'] = node['node']
                        self.state['proxmox']['config'] = config
                        self.save()
                        break
                except Exception as e:
                    pass
            pass

        return self.state['proxmox']

    def update_powerdns(self):
        # TODO Check and create/update powerdns records
        pass

    def update_freeipa(self):
        # TODO Check and create/update IPA Hosts to prepare for client-install
        pass

    def update_awx(self):
        # TODO Add host to AWX inventory, and check that is have the correct "playbooks"
        pass

    def update_monitoring(self):
        # TODO Generate prometheus job that will generate files for ICMP monitoring
        pass
