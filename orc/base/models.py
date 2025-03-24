from django.db import models
from django_extensions.db.fields import ShortUUIDField

import re
import pynetbox
import proxmoxer
import python_freeipa

from orc.base.providers.pdns_class import PowerDNS


class Platform(models.Model):
    id = ShortUUIDField(primary_key=True, unique=True, editable=False)
    name = models.CharField(max_length=64)

    ipam_provider_config = models.JSONField()
    dns_forward_provider_config = models.JSONField(blank=True, null=True)
    dns_reverse_provider_config = models.JSONField(blank=True, null=True)
    vm_provider_config = models.JSONField(blank=True, null=True)
    configuration_management_provider_config = models.JSONField(
        blank=True, null=True)
    identity_management_provider_config = models.JSONField(
        blank=True, null=True)

    tags = models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def networks(self):
        return Network.objects.filter(platform_id=self.id)

    def instance_templates(self):
        return InstanceTemplate.objects.filter(platform_id=self.id)

    def __str__(self):
        return self.name

    def ipam(self):
        if self.ipam_provider_config is None:
            return None

        if self.ipam_provider_config['type'] == 'netbox':
            return pynetbox.api(
                self.ipam_provider_config['url'],
                token=self.ipam_provider_config['token']
            )

    def dns_forward(self):
        if self.dns_forward_provider_config is None:
            return None

        if self.dns_forward_provider_config['type'] == 'pdns':
            return PowerDNS(self.dns_forward_provider_config['url'], self.dns_forward_provider_config['apikey'])

    def dns_reverse(self):
        if self.dns_reverse_provider_config is None:
            return None

        if self.dns_reverse_provider_config['type'] == 'pdns':
            return PowerDNS(self.dns_reverse_provider_config['url'], self.dns_reverse_provider_config['apikey'])

    def identity_management(self):
        if self.identity_management_provider_config is None:
            return None

        if self.identity_management_provider_config['type'] == 'freeipa':
            client = python_freeipa.ClientMeta(
                host=self.identity_management_provider_config['host'], verify_ssl=False)
            client.login(
                self.identity_management_provider_config['user'], self.identity_management_provider_config['password'])
            return client

    def vm(self):
        if self.vm_provider_config is None:
            return None

        if self.vm_provider_config['type'] == 'pve':
            return proxmoxer.ProxmoxAPI(
                self.vm_provider_config['url'],
                user=self.vm_provider_config['user'],
                token_name=self.vm_provider_config['token_name'],
                token_value=self.vm_provider_config['token_value'],
                verify_ssl=False
            )


class Network(models.Model):
    id = ShortUUIDField(primary_key=True, unique=True, editable=False)
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)

    dns_reverse_provider_config = models.JSONField(blank=True, null=True)
    ipam_provider_state = models.JSONField()
    vm_provider_state = models.JSONField(blank=True, null=True)
    dns_reverse_provider_state = models.JSONField(blank=True, null=True)

    tags = models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_vlan_id(self):
        if self.platform.ipam_provider_config is None or self.ipam_provider_state is None:
            return None

        if self.platform.ipam_provider_config['type'] == 'netbox' and 'vlan_id' in self.ipam_provider_state:
            return self.platform.ipam().ipam.vlans.get(
                self.ipam_provider_state['vlan_id']).vid

    def get_prefixes(self):
        if self.platform.ipam_provider_config is None or self.ipam_provider_state is None:
            return None

        if self.platform.ipam_provider_config['type'] == 'netbox' and 'vlan_id' in self.ipam_provider_state:
            nb_prefixes = list(
                self.platform.ipam().ipam.prefixes.filter(
                    vlan_id=self.ipam_provider_state['vlan_id']))
            prefixes_v4 = []
            prefixes_v6 = []
            for prefix in nb_prefixes:
                if prefix.family.value == 4:
                    prefixes_v4.append(prefix.prefix)
                elif prefix.family.value == 6:
                    prefixes_v6.append(prefix.prefix)
            return {
                "ipv4": prefixes_v4,
                "ipv6": prefixes_v6
            }

    def get_available_ips_v4(self):
        if self.platform.ipam_provider_config is None or self.ipam_provider_state is None:
            return None

        if self.platform.ipam_provider_config['type'] == 'netbox' and 'vlan_id' in self.ipam_provider_state:
            nb_prefixes = list(
                self.platform.ipam().ipam.prefixes.filter(
                    vlan_id=self.ipam_provider_state['vlan_id']))
            available_ips_v4 = []
            for prefix in nb_prefixes:
                if prefix.family.value == 4:
                    for ip in prefix.available_ips.list():
                        available_ips_v4.append(ip.address)
            return available_ips_v4

    def get_next_ip(self):
        ipv4 = str(self.get_available_ips_v4()[0])
        prefix6 = self.get_prefixes()['ipv6'][0]
        p = re.compile('(.*)\\.(.*)\\.(.*)\\.(.*)/(.*)')
        m = p.match(ipv4)
        ipv4_last = m.group(4)
        p = re.compile('(.*)::/(.*)')
        m = p.match(str(prefix6))
        ipv6 = "{0}::{1}/{2}".format(m.group(1), ipv4_last, m.group(2))

        return {
            "ipv4": ipv4,
            "ipv6": ipv6
        }

    def get_vrf(self):
        if self.platform.ipam_provider_config is None or self.ipam_provider_state is None and self.platform.ipam_provider_config['type'] != 'netbox':
            return None

        if self.platform.ipam_provider_config['type'] == 'netbox' and 'vlan_id' in self.ipam_provider_state:
            nb_prefixes = list(
                self.platform.ipam().ipam.prefixes.filter(
                    vlan_id=self.ipam_provider_state['vlan_id']))
            if len(nb_prefixes) < 1 and nb_prefixes[0]['vrf'] is None:
                return None
            vrf = nb_prefixes[0]['vrf']
            return {"id": vrf["id"], "name": vrf["name"]}


class InstanceTemplate(models.Model):
    id = ShortUUIDField(primary_key=True, unique=True, editable=False)
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)

    vm_provider_state = models.JSONField(blank=True, null=True)

    tags = models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Instance(models.Model):
    id = ShortUUIDField(primary_key=True, unique=True, editable=False)
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    template = models.ForeignKey(
        InstanceTemplate,
        on_delete=models.CASCADE,
        null=True
    )
    name = models.CharField(max_length=64)
    config = models.JSONField()
    tags = models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    ipam_provider_state = models.JSONField(blank=True, null=True, default=None)
    dns_forward_provider_state = models.JSONField(blank=True, null=True)
    dns_reverse_provider_state = models.JSONField(blank=True, null=True)
    vm_provider_state = models.JSONField(blank=True, null=True)
    configuration_management_provider_state = models.JSONField(
        blank=True, null=True)
    identity_management_provider_state = models.JSONField(
        blank=True, null=True)

    def __str__(self):
        return self.name
