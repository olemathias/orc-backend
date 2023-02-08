import time

from django_rq import job
from orc.base.models import Instance

from .proxmox import *

@job
def create_qemu_vm_job(instance_id, pve_node_name):
    vm = Instance.objects.get(id=instance_id)
    if 'proxmox' in vm.state and 'id' in vm.state['proxmox'] and vm.state['proxmox']['id'] is None:
        return False

    if 'proxmox' not in vm.state:
        vm.state['proxmox'] = {}

    pve_node = vm.platform.proxmox().nodes(pve_node_name)
    if pve_node is None:
        raise Exception('Failed to connect to pve node')
    pve_vm_template = find_pve_template(pve_node, vm.template)
    if pve_vm_template is None:
        raise Exception('VM Template not found, or more then one found')
    pve_vm_template_status = pve_vm_template.status().current.get()

    pve_vm_id = vm.platform.proxmox().cluster.nextid.get()
    vm.state['proxmox']['id'] = pve_vm_id
    vm.state['proxmox']['status'] = "provisioning"
    vm.state['proxmox']['template'] = { pve_vm_template_status['vmid']: pve_vm_template_status['name'] }
    vm.state['proxmox']['node'] = pve_node_name
    vm.save()

    create_cloudinit_userdata(pve_node_name, vm)

    pve_clone_job_id = pve_vm_template.clone.post(
        newid=pve_vm_id,
        description="{}".format("just a test"),
        name=vm.name,
        full=1,
        target=pve_node_name
    )

    ip4 = "{}/{}".format(vm.config['net']['ipv4']['ip'], vm.config['net']['ipv4']['prefixlen'])
    ip6 = "{}/{}".format(vm.config['net']['ipv6']['ip'], vm.config['net']['ipv6']['prefixlen'])
    gw4 = vm.config['net']['ipv4']['gw']
    gw6 = vm.config['net']['ipv6']['gw']
    wait_for_job(pve_node, pve_clone_job_id)
    new_vm = pve_node.qemu(pve_vm_id)
    new_vm.config.post(
        memory=int(vm.config['hw']['memory'])*1024,
        cores=int(vm.config['hw']['cpu_cores']),
        net0="virtio,firewall={0},bridge={1},tag={2}".format(int(vm.config['net']['firewall']), vm.platform.config['proxmox']['nodes'][pve_node_name]['vmbridge'], vm.config['net']['vlan_id']),
        ipconfig0="gw={},gw6={},ip={},ip6={}".format(gw4, gw6, ip4, ip6),
        searchdomain=vm.platform.config['domain'],
        cicustom='user={}/cloudinit_user_{}.yaml'.format('local:snippets', pve_vm_id)
    )
    new_vm.resize.put(
        disk='scsi0',
        size="{}G".format(vm.config['hw']['os_disk'])
    )
    wait_for_job(pve_node,new_vm.status.start.post())
    time.sleep(1) # Just to make sure status is changed to running
    if vm.config['net']['firewall']:
        new_vm.firewall.ipset.post(name='ipfilter-net0')
        new_vm.firewall.ipset('ipfilter-net0').post(cidr="{}/32".format(vm.config['net']['ipv4']['ip']))
        new_vm.firewall.ipset('ipfilter-net0').post(cidr="{}/128".format(vm.config['net']['ipv6']['ip']))
        new_vm.firewall.options.put(
            enable=1,
            dhcp=0,
            ipfilter=1,
            macfilter=1,
            ndp=1,
            radv=0,
            policy_in='ACCEPT',
            policy_out='ACCEPT'
        )
    wait_for_poweroff(pve_node, pve_vm_id)

    # Delete CloudInit disk
    new_vm.config.post(
        delete='scsi1'
    )

    if 'additional_net' in vm.config:
        new_vm.config.post(
            net1="virtio,firewall={0},bridge={1},tag={2}".format(int(vm.config['additional_net']['firewall']), vm.config['additional_net']['vmbridge'], vm.config['additional_net']['vlan_id'])
        )

    new_vm.status.start.post()

    vm.state['proxmox']['status'] = "provisioned"
    vm.save()
    vm.update_state()

    cleanup_cloudinit(pve_node_name, vm)

@job
def restart_qemu_vm_job(vm_id):
    vm = Vm.objects.get(id=vm_id)
    if 'proxmox' not in vm.state or 'id' not in vm.state['proxmox'] or vm.state['proxmox']['id'] is None:
        return False

    pve_node, pve_vm = vm.get_pve_node_and_vm()
    if pve_node is None or pve_vm is None:
        return False

    pve_vm.status.reboot.post()
    return True

@job
def delete_qemu_vm_job(vm_id):
    vm = Vm.objects.get(id=vm_id)
    if 'proxmox' in vm.state and 'id' in vm.state['proxmox'] and vm.state['proxmox']['id'] is None:
        return False

    pve_node, pve_vm = vm.get_pve_node_and_vm()
    if pve_node is None or pve_vm is None:
        return False

    wait_for_job(pve_node, pve_vm.status.stop.post())
    wait_for_poweroff(pve_node, vm.state['proxmox']['id'])
    wait_for_job(pve_node, pve_vm.delete())
    del vm.state['proxmox']
    vm.delete_vm()

    return True