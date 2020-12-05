from django.db import models
from django.conf import settings

import re
import pynetbox
import proxmoxer
import python_freeipa
from towerlib import Tower
from ipam.pdns import PowerDNS

def remove_secrets(obj, rubbish):
    if isinstance(obj, dict):
        obj = {
            key: remove_secrets(value, rubbish)
            for key, value in obj.items()
            if key not in rubbish}
    elif isinstance(obj, list):
        obj = [remove_secrets(item, rubbish)
                  for item in obj
                  if item not in rubbish]
    return obj

class Environment(models.Model):
    name = models.CharField(max_length=256)
    config = models.JSONField()
    state = models.JSONField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    nb_cluster = None

    def stripped_config(self):
        secrets = ('token', 'ssh_authorized_keys', 'token_value', 'private_ssh_key', 'key', 'password')
        return remove_secrets(self.config, secrets)

    @property
    def active_providers(self):
        return ['netbox', 'proxmox', 'powerdns', 'freeipa', 'awx']

    def netbox(self):
        return pynetbox.api(
            self.config['netbox']['url'],
            token=self.config['netbox']['token']
        )

    def proxmox(self):
        return proxmoxer.ProxmoxAPI(
            self.config['proxmox']['url'],
            user=self.config['proxmox']['user'],
            token_name=self.config['proxmox']['token_name'],
            token_value=self.config['proxmox']['token_value'],
            verify_ssl=False
        )

    def powerdns(self):
        return PowerDNS(self.config['powerdns']['url'], self.config['powerdns']['key'])

    def freeipa(self):
        client = python_freeipa.ClientMeta(host=self.config['freeipa']['host'], verify_ssl=False)
        client.login(self.config['freeipa']['user'], self.config['freeipa']['password'])
        return client

    def awx(self):
        return Tower(self.config['awx']['host'], self.config['awx']['user'], self.config['awx']['password'], secure=False)

    @property
    def site_id(self):
        self.fetch_from_netbox_cluster()
        return self.nb_cluster.site.id

    @property
    def cluster_id(self):
        self.fetch_from_netbox_cluster()
        return self.nb_cluster.id

    def fetch_from_netbox_cluster(self):
        if self.nb_cluster is None:
            self.nb_cluster = self.netbox().virtualization.clusters.get(self.state['netbox']['cluster_id'])

    def __str__(self):
        return self.name

# Create your models here.
class Network(models.Model):
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE)
    config = models.JSONField()
    state = models.JSONField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    nb_vlan = None
    nb_prefixes = None

    def __str__(self):
        available_ips = len(self.get_available_ips())
        if available_ips == 50:
            available_ips = "50+"
        return "{} (VLAN: {}) - {} free IPs".format(self.name, self.vid, available_ips)

    @property
    def vid(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.vid

    @property
    def name(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.name

    @property
    def display_name(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.display_name

    @property
    def description(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.description

    @property
    def prefixes4(self):
        self.fetch_from_netbox_prefixes()
        prefixes = []
        for prefix in self.nb_prefixes:
            if prefix.family.value == 4:
                prefixes.append(prefix.prefix)
        return prefixes

    @property
    def prefixes6(self):
        self.fetch_from_netbox_prefixes()
        prefixes = []
        for prefix in self.nb_prefixes:
            if prefix.family.value == 6:
                prefixes.append(prefix.prefix)
        return prefixes

    def get_available_ips(self):
        self.fetch_from_netbox_prefixes()
        available_ips_v4 = []
        for prefix in self.nb_prefixes:
            if prefix.family.value == 4:
                for ip in prefix.available_ips.list():
                    available_ips_v4.append(ip.address)
        return available_ips_v4

    def get_next_ip(self):
        ipv4 = str(self.get_available_ips()[0])
        p = re.compile('(.*)\.(.*)\.(.*)\.(.*)/(.*)')
        m = p.match(ipv4)
        ipv4_last = m.group(4)
        p = re.compile('(.*)::/(.*)')
        m = p.match(str(self.prefixes6[0]))
        ipv6 = "{0}::{1}/{2}".format(m.group(1), ipv4_last, m.group(2))

        return {
            "ipv4": ipv4,
            "ipv6": ipv6
        }

    def fetch_from_netbox_vlan(self):
        if self.nb_vlan is None:
            self.nb_vlan = self.environment.netbox().ipam.vlans.get(self.state['netbox']['id'])

    def fetch_from_netbox_prefixes(self):
        if self.nb_prefixes is None:
            self.nb_prefixes = self.environment.netbox().ipam.prefixes.filter(vlan_id=self.state['netbox']['id'])
