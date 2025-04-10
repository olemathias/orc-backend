def create_vm(instance, data, vrf, ipv4, ipv6):
    ipam_instance_vm = None
    vrf_id = vrf["id"] if vrf is not None else None
    if instance.ipam_provider_state is None:
        instance.ipam_provider_state = {}
    if 'vm_id' not in instance.ipam_provider_state:
        ipam_instance_vm = instance.platform.ipam().virtualization.virtual_machines.create(
            name=instance.name,
            cluster=instance.platform.ipam_provider_config['cluster_id'],
            vcpus=data['cpu_cores'],
            memory=int(
                data['memory']) * 1024,
            disk=int(
                data['os_disk']),
            status='active')
        instance.ipam_provider_state = {
            "type": "netbox", "vm_id": ipam_instance_vm.id
        }

    if ipam_instance_vm is None:
        ipam_instance_vm = instance.platform.ipam().virtualization.virtual_machines.get(
            instance.ipam_provider_state['vm_id'])

    if instance.platform.ipam().virtualization.interfaces.get(
            virtual_machine_id=ipam_instance_vm.id, name="eth0") is None:
        ipam_instance_interface = instance.platform.ipam().virtualization.interfaces.create(
            virtual_machine=ipam_instance_vm.id, name='eth0')
        ipam_instance_ipv4 = instance.platform.ipam().ipam.ip_addresses.create(
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=ipam_instance_interface['id'],
            address=str(ipv4),
            status="active",
            vrf=vrf_id
        )
        ipam_instance_ipv6 = instance.platform.ipam().ipam.ip_addresses.create(
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=ipam_instance_interface['id'],
            address=str(ipv6),
            status="active",
            vrf=vrf_id
        )
        ipam_instance_vm.primary_ip4 = ipam_instance_ipv4['id']
        ipam_instance_vm.primary_ip6 = ipam_instance_ipv6['id']
        ipam_instance_vm.save()

        if 'interface' not in instance.ipam_provider_state:
            instance.ipam_provider_state['interface'] = []
        instance.ipam_provider_state['interface'].append(
            {'id': ipam_instance_interface['id'],
             'name': ipam_instance_interface['name']}
        )

        if 'ip_addresses' not in instance.ipam_provider_state:
            instance.ipam_provider_state['ip_addresses'] = []
        instance.ipam_provider_state['ip_addresses'].append(
            {
                'id': ipam_instance_ipv4['id'],
                'address': ipam_instance_ipv4['address'],
                'interface_id': ipam_instance_ipv4['assigned_object_id'],
                'vrf': vrf_id
            }
        )
        instance.ipam_provider_state['ip_addresses'].append(
            {
                'id': ipam_instance_ipv6['id'],
                'address': ipam_instance_ipv6['address'],
                'interface_id': ipam_instance_ipv6['assigned_object_id'],
                'vrf': vrf_id
            }
        )

        instance.ipam_provider_state['status'] = "provisioned"


def delete_vm(instance):
    if 'type' in instance.ipam_provider_state and instance.ipam_provider_state['type'] == 'netbox' and 'vm_id' in instance.ipam_provider_state and instance.ipam_provider_state['vm_id'] is None:
        return False

    vm = instance.platform.ipam().virtualization.virtual_machines.get(
        instance.ipam_provider_state['vm_id'])
    vm.delete()
    return True
