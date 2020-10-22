from django.db import models
from django.conf import settings
from ipam.models import Network, Environment

import ipaddress

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

    @property
    def fqdn(self):
        return "{}.{}".format(self.name, self.environment.config['domain'])

    @property
    def status(self):
        status = []
        for key, state in self.state.items():
            if 'status' in state:
                status.append(state['status'])
        if 'provisioning' in status:
            return 'provisioning'
        if 'error' in status:
            return 'error'
        if 'destroying' in status:
            return 'destroying'
        if 'provisioned' in status:
            return 'provisioned'
        return 'unknown'

    def update_state(self):
        self.update_netbox()
        self.update_powerdns()
        self.update_freeipa()
        self.update_awx()
        self.update_proxmox()
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
                address="{}/{}".format(self.config['net']['ipv4']['ip'], self.config['net']['ipv4']['prefixlen']),
                status="active"
             )
            ipv6 = self.environment.netbox().ipam.ip_addresses.create(
                assigned_object_type="virtualization.vminterface",
                assigned_object_id=interface['id'],
                address="{}/{}".format(self.config['net']['ipv6']['ip'], self.config['net']['ipv6']['prefixlen']),
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
            self.state['netbox']['status'] = "provisioned"
            self.save()

        return self.state['netbox']

    def update_proxmox(self):
        proxmox = self.environment.proxmox()
        if 'proxmox' not in self.state:
            self.state['proxmox'] = {}
            self.save()
            from vms.proxmox import create_qemu_vm_job
            create_qemu_vm_job.delay(self.pk, 'pve1')

        if 'proxmox' in self.state and 'id' in self.state['proxmox'] and self.state['proxmox']['id'] is not None:
            vm = None
            for node in proxmox.nodes.get():
                try:
                    vm = proxmox.nodes(node['node']).qemu(self.state['proxmox']['id'])
                    if vm is not None:
                        status = vm.status().current.get()
                        config = vm.config().get()
                        self.state['proxmox']['name'] = status['name']
                        self.state['proxmox']['vm_status'] = status['status']
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
                    "content": self.config['net']['ipv4']['ip'],
                    "disabled": False,
                    "type": "A"
                }],
                "ttl": 900
            })
            rrsets.append({
                "name": fqdn,
                "changetype": "replace",
                "type": "AAAA",
                "records": [{
                    "content": self.config['net']['ipv6']['ip'],
                    "disabled": False,
                    "type": "AAAA"
                }],
                "ttl": 900
            })

            print(self.environment.powerdns().set_records(self.environment.config['domain']+".", rrsets))
            self.state['powerdns'] = {}
            self.state['powerdns']['domains'] = {}
            self.state['powerdns']['domains'][self.environment.config['domain']+"."] = rrsets
            self.save()

            rdns_v4_zones = self.environment.powerdns().search("*.in-addr.arpa", 2000, "zone")
            v4_ptr = ipaddress.IPv4Address(self.config['net']['ipv4']['ip']).reverse_pointer
            rdns_v4_zone = None
            for zone in [ sub['name'] for sub in rdns_v4_zones ]:
                test = str(v4_ptr).split('.')
                for i in range(len(test)-2):
                    x = len(test) - i
                    print(".".join(test[-x:])+'.')
                    if ".".join(test[-x:])+'.' in zone:
                        rdns_v4_zone = zone
                        break
            rdns_v6_zones = self.environment.powerdns().search("*.ip6.arpa", 2000, "zone")
            v6_ptr = ipaddress.IPv6Address(self.config['net']['ipv6']['ip']).reverse_pointer
            rdns_v6_zone = None
            for zone in [ sub['name'] for sub in rdns_v6_zones ]:
                test = str(v6_ptr).split('.')
                for i in range(len(test)-2):
                    x = len(test) - i
                    print(".".join(test[-x:])+'.')
                    if ".".join(test[-x:])+'.' in zone:
                        rdns_v6_zone = zone
                        break

            if rdns_v4_zone is not None:
                rrsets = []
                rrsets.append({
                    "name": v4_ptr+'.',
                    "changetype": "replace",
                    "type": "PTR",
                    "records": [{
                        "content": fqdn,
                        "disabled": False,
                        "type": "PTR"
                    }],
                    "ttl": 900
                })
                print(rrsets)
                print(self.environment.powerdns().set_records(rdns_v4_zone, rrsets))
                self.state['powerdns']['domains'][rdns_v4_zone] = rrsets
                self.save()

            if rdns_v6_zone is not None:
                rrsets = []
                rrsets.append({
                    "name": v6_ptr+'.',
                    "changetype": "replace",
                    "type": "PTR",
                    "records": [{
                        "content": fqdn,
                        "disabled": False,
                        "type": "PTR"
                    }],
                    "ttl": 900
                })
                print(rrsets)
                print(self.environment.powerdns().set_records(rdns_v6_zone, rrsets))
                self.state['powerdns']['domains'][rdns_v6_zone] = rrsets
                self.save()

            self.state['powerdns']['status'] = "provisioned"

        return self.state['powerdns']

    def update_freeipa(self):
        fqdn = "{}.{}".format(self.name, self.environment.config['domain'])
        if 'freeipa' not in self.state:
            client = self.environment.freeipa()
            print(client.host_add(fqdn, o_ip_address=self.config['net']['ipv4']['ip']))
            self.state['freeipa'] = {"fqdn": fqdn}
            self.state['freeipa']['status'] = "provisioned"
            self.save()
        pass

    def update_awx(self):
        fqdn = "{}.{}".format(self.name, self.environment.config['domain'])
        if 'awx' not in self.state:
            client = self.environment.awx()
            client.create_host_in_inventory(inventory=self.environment.config['awx']['inventory'], name=fqdn, description="orc_managed", organization=self.environment.config['awx']['organization'])
            self.state['awx'] = {"fqdn": fqdn, "inventory": self.environment.config['awx']['inventory']}
            self.state['awx']['status'] = "provisioned"
            self.save()
        if 'awx_templates' not in self.state:
            self.state['awx_templates'] = {}
            self.save()
        if 'awx_templates' in self.config:
            for key, template in self.config['awx_templates'].items():
                if key not in self.state['awx_templates']:
                    self.state['awx_templates'][key] = {"status": "new"}
                    self.save()
                if key in self.state['awx_templates'] and self.state['awx_templates'][key]["status"] in ["successful", "provisioned", "provisioning", "pending"]:
                    continue

                requirements_met = True
                if 'trigger' in template:
                    if 'after_state' in template['trigger']:
                        for t in template['trigger']['after_state']:
                            if t not in self.state or self.state[t]["status"] not in ["provisioned"]:
                                requirements_met = False
                if requirements_met:
                    self.state['awx_templates'][key] = {"status": "provisioning"}
                    from vms.jobs import run_awx_template_job
                    run_awx_template_job.delay(self.pk, template['id'], key)
                    break
                else:
                    self.state['awx_templates'][key] = {"status": "missing_dependency"}

        return self.state['awx']

    def update_monitoring(self):
        # TODO Generate prometheus job that will generate files for ICMP monitoring
        pass

    def delete_vm(self):
        self.delete_from_proxmox()
        self.delete_from_freeipa()
        self.delete_from_awx()
        self.delete_from_powerdns()

        # Only delete host from netbox and orc after host is removed from Proxmox
        if 'proxmox' not in self.state:
            self.delete_from_netbox()
            self.delete()

    def delete_from_netbox(self):
        if 'netbox' not in self.state or 'id' not in self.state['netbox']:
            return False
        vm = self.environment.netbox().virtualization.virtual_machines.get(self.state['netbox']['id'])
        vm.delete()
        del self.state['netbox']
        self.save()
        return True

    def delete_from_proxmox(self):
        proxmox = self.environment.proxmox()
        if 'proxmox' not in self.state or 'id' not in self.state['proxmox'] or self.state['proxmox']['id'] is None:
            return False

        self.state['proxmox']['status'] = "destroying"
        self.save()

        from vms.proxmox import delete_qemu_vm_job
        delete_qemu_vm_job.delay(self.pk)

        return True

    def delete_from_powerdns(self):
        if 'powerdns' not in self.state or 'domains' not in self.state['powerdns']:
           return False

        for domain in list(self.state['powerdns']['domains']):
            rrsets = []
            for rrset in self.state['powerdns']['domains'][domain]:
                rrset['changetype'] = "delete"
                rrsets.append(rrset)
            print(self.environment.powerdns().set_records(domain, rrsets))
            del self.state['powerdns']['domains'][domain]
            self.save()
        del self.state['powerdns']
        self.save()
        return True

    def delete_from_freeipa(self):
        if 'freeipa' not in self.state or 'fqdn' not in self.state['freeipa']:
            return False
        print(self.environment.freeipa().host_del(self.state['freeipa']['fqdn']))
        del self.state['freeipa']
        self.save()
        return True

    def delete_from_awx(self):
        if 'awx' not in self.state or 'fqdn' not in self.state['awx'] or 'inventory' not in self.state['awx']:
            return False
        client = self.environment.awx()
        client.delete_inventory_host(inventory=self.state['awx']['inventory'], name=self.state['awx']['fqdn'], organization=self.environment.config['awx']['organization'])
        del self.state['awx']
        del self.state['awx_templates']
        self.save()
        return True
