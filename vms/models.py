from django.db import models
from django.conf import settings
from ipam.models import Network

import pynetbox

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
    vm_id = models.IntegerField(null=True)
    host_cluster = models.ForeignKey(HostCluster, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    config = models.JSONField()
    status = models.CharField(max_length=64)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    nb = pynetbox.api(
        settings.NETBOX_URL,
        token=settings.NETBOX_TOKEN
    )

    def __str__(self):
        return self.name

    def update_netbox(self):
        netbox_vm_create = self.nb.virtualization.virtual_machines.create(
            name=self.name,
            site=self.host_cluster.get_site_id(),
            cluster=self.host_cluster.netbox_cluster_id,
            role=self.config['role'],
            vcpus=self.config['hw']['cpu_cores'],
            memory=int(self.config['hw']['memory'])*1024,
            disk=int(self.config['hw']['os_disk']),
            status='active'
        )

        netbox_interface = self.nb.virtualization.interfaces.create(
            virtual_machine=netbox_vm_create['id'],
            name='eth0'
        )

        netbox_ipv4 = self.nb.ipam.ip_addresses.create(
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=netbox_interface['id'],
            address="{}/{}".format(self.config['config']['ipv4']['ip'], self.config['config']['ipv4']['prefixlen']),
            status="active"
         )

        netbox_ipv6 = self.nb.ipam.ip_addresses.create(
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=netbox_interface['id'],
            address="{}/{}".format(self.config['config']['ipv6']['ip'], self.config['config']['ipv6']['prefixlen']),
            status="active"
        )

        netbox_vm = self.nb.virtualization.virtual_machines.get(netbox_vm_create['id'])
        netbox_vm.primary_ip4 = netbox_ipv4['id']
        netbox_vm.primary_ip6 = netbox_ipv6['id']
        netbox_vm.save()
        return True
