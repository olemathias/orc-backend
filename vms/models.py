from django.db import models
from django.conf import settings
from ipam.models import Network, Environment
from jobs.models import Job

class Vm(models.Model):
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    config = models.JSONField()
    state = models.JSONField()
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

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
            vm = self.environment.netbox().virtualization.virtual_machines.create(
                name=self.name,
                site=self.environment.get_site_id(),
                cluster=self.environment.get_cluster_id(),
                role=self.config['role'],
                vcpus=self.config['hw']['cpu_cores'],
                memory=int(self.config['hw']['memory'])*1024,
                disk=int(self.config['hw']['os_disk']),
                status='active'
            )
            self.state['netbox']['id'] = vm.id
            self.save()

        if vm is None:
            vm = self.environment.netbox().virtualization.virtual_machines.get(self.state['netbox']['id'])

        if self.environment.netbox().virtualization.interfaces.get(virtual_machine_id=vm.id, name="eth0") is None:
            interface = self.environment.netbox().virtualization.interfaces.create(
                virtual_machine=vm.id,
                name='eth0'
            )
            ipv4 = self.environment.netbox().ipam.ip_addresses.create(
                assigned_object_type="virtualization.vminterface",
                assigned_object_id=interface['id'],
                address="{}/{}".format(self.config['config']['ipv4']['ip'], self.config['config']['ipv4']['prefixlen']),
                status="active"
             )
            ipv6 = self.environment.netbox().ipam.ip_addresses.create(
                assigned_object_type="virtualization.vminterface",
                assigned_object_id=interface['id'],
                address="{}/{}".format(self.config['config']['ipv6']['ip'], self.config['config']['ipv6']['prefixlen']),
                status="active"
            )
            vm.primary_ip4 = ipv4['id']
            vm.primary_ip6 = ipv6['id']
            vm.save()

            if 'interface' not in self.state['netbox']:
                self.state['netbox']['interface'] = []
            self.state['netbox']['interface'].append({'id': interface['id'], 'name': interface['name']})

            if 'ip_addresses' not in self.state['netbox']:
                self.state['netbox']['ip_addresses'] = []
            self.state['netbox']['ip_addresses'].append({'id': ipv4['id'], 'address': ipv4['address'], 'interface_id': ipv4['assigned_object_id']})
            self.state['netbox']['ip_addresses'].append({'id': ipv6['id'], 'address': ipv6['address'], 'interface_id': ipv6['assigned_object_id']})
            self.save()

        return self.state['netbox']

    def update_proxmox(self):
        proxmox = self.environment.proxmox()
        if 'proxmox' not in self.state:
            self.state['proxmox'] = {"id": None}
            self.save()
            job = Job(task="create_vm", status="new")
            job.description = "Create VM {} in {}".format(self.name, self.environment)
            job.job = {**self.config, **{"vm_id": self.pk}, **{"state": self.state}}
            job.save()

        if 'id' in self.state['proxmox'] and self.state['proxmox']['id'] is not None:
            vm = None
            for node in proxmox.nodes.get():
                try:
                    vm = proxmox.nodes(node['node']).qemu(self.state['proxmox']['id'])
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
        fqdn = "{}.{}.".format(self.name, self.environment.config['domain'])
        if 'powerdns' not in self.state:
            rrsets = []
            rrsets.append({
                "name": fqdn,
                "changetype": "replace",
                "type": "A",
                "records": [{
                    "content": self.config['config']['ipv4']['ip'],
                    "disabled": False,
                    "type": "A",
                    "set-ptr": True
                }],
                "ttl": 900
            })
            rrsets.append({
                "name": fqdn,
                "changetype": "replace",
                "type": "AAAA",
                "records": [{
                    "content": self.config['config']['ipv6']['ip'],
                    "disabled": False,
                    "type": "AAAA",
                    "set-ptr": True
                }],
                "ttl": 900
            })
            print(self.environment.powerdns().set_records(rrsets))
            self.state['powerdns'] = rrsets

        return self.state['powerdns']

    def update_freeipa(self):
        fqdn = "{}.{}".format(self.name, self.environment.config['domain'])
        if 'freeipa' not in self.state:
            client = self.environment.freeipa()
            print(client.host_add(fqdn, o_ip_address=self.config['config']['ipv4']['ip']))
            self.state['freeipa'] = {"fqdn": fqdn}
            self.save()
        pass

    def update_awx(self):
        fqdn = "{}.{}".format(self.name, self.environment.config['domain'])
        if 'awx' not in self.state:
            client = self.environment.awx()
            client.create_host_in_inventory(inventory=self.environment.config['awx']['inventory'], name=fqdn, description="orc_managed", organization=self.environment.config['awx']['organization'])
            self.state['awx'] = {"fqdn": fqdn, "inventory": self.environment.config['awx']['inventory']}
            self.save()
        pass

    def update_monitoring(self):
        # TODO Generate prometheus job that will generate files for ICMP monitoring
        pass
