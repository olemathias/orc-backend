from django.db import models
from django.conf import settings

import re
import pynetbox

# Create your models here.
class Network(models.Model):
    source_id = models.IntegerField()
    role = models.CharField(max_length=16)
    created = models.DateTimeField(auto_now_add=True)


    nb = pynetbox.api(
        settings.NETBOX_URL,
        token=settings.NETBOX_TOKEN
    )
    nb_vlan = None
    nb_prefixes = None

    def __str__(self):
        return "{} (VLAN: {}) - {} free IPs".format(self.name(), self.vid(), len(self.get_available_ips()))

    def vid(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.vid

    def name(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.name

    def display_name(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.display_name

    def description(self):
        self.fetch_from_netbox_vlan()
        return self.nb_vlan.description

    def prefixes4(self):
        self.fetch_from_netbox_prefixes()
        prefixes = []
        for prefix in self.nb_prefixes:
            if prefix.family.value == 4:
                prefixes.append(prefix.prefix)
        return prefixes

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
        m = p.match(str(self.prefixes6()[0]))
        ipv6 = "{0}::{1}/{2}".format(m.group(1), ipv4_last, m.group(2))

        return {
        "ipv4": ipv4,
        "ipv6": ipv6
        }

    def fetch_from_netbox_vlan(self):
        if self.nb_vlan is None:
            self.nb_vlan = self.nb.ipam.vlans.get(self.source_id)

    def fetch_from_netbox_prefixes(self):
        if self.nb_prefixes is None:
            self.nb_prefixes = self.nb.ipam.prefixes.filter(vlan_id=self.source_id)
