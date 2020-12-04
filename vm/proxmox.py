import yaml
import time
import json
import requests
import re

from django_rq import job
from vm.models import Vm

import io
import paramiko
from scp import SCPClient

def find_pve_template(pve_node, template):
    pve_vm_templates = []
    for t in pve_node.qemu.get():
        if re.match(template.config['pve_template'], t['name']) is not None:
            pve_vm_templates.append(pve_node.qemu(t['vmid']))

    # Only return if we have one match
    if len(pve_vm_templates) == 1:
        return pve_vm_templates[0]
    return None


@job
def create_qemu_vm_job(vm_id, pve_node_name):
    vm = Vm.objects.get(id=vm_id)
    if 'proxmox' in vm.state and 'id' in vm.state['proxmox'] and vm.state['proxmox']['id'] is None:
        return False

    if 'proxmox' not in vm.state:
        vm.state['proxmox'] = {}

    pve_node = vm.environment.proxmox().nodes(pve_node_name)
    pve_vm_template = find_pve_template(pve_node, vm.template)
    if pve_vm_template is None:
        raise Exception('VM Template not found, or more then one found')
    pve_vm_template_status = pve_vm_template.status().current.get()

    pve_vm_id = vm.environment.proxmox().cluster.nextid.get()
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
        net0="virtio,firewall={0},bridge={1},tag={2}".format(int(vm.config['net']['firewall']), vm.environment.config['proxmox']['nodes'][pve_node_name]['vmbridge'], vm.config['net']['vlan_id']),
        ipconfig0="gw={},gw6={},ip={},ip6={}".format(gw4, gw6, ip4, ip6),
        searchdomain=vm.environment.config['domain'],
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

def wait_for_poweroff(node, pve_vm_id):
    running = True
    while running:
        vm = node.qemu(pve_vm_id)
        if vm.status.current.get()['status'] != 'running':
            running = False
        time.sleep(2)
    return vm.status.current.get()['status']

def wait_for_job(node, pve_job_id):
    running = True
    while running:
        task = (node.tasks(pve_job_id)).status.get()
        if task['status'] != 'running':
            running = False
        time.sleep(2)
    return task['status']

def create_cloudinit_userdata(pve_node_name, vm):
    node_config = vm.environment.config['proxmox']['nodes'][pve_node_name]

    user = vm.template.config['user'] if 'user' in vm.template.config and vm.template.config['user'] is not None else 'debian'

    data = {
        'hostname': vm.name,
        'fqdn': '{}.{}'.format(vm.name, vm.environment.config['domain']),
        'user': user,
        'ssh_authorized_keys': vm.environment.config['proxmox']['ssh_authorized_keys'],
        'chpasswd': {'expire': False},
        'users': ['default'],
        'package_upgrade': True,
        'runcmd': get_run_cmd(vm),
        'bootcmd': ['echo "nameserver 1.1.1.1" > /etc/resolv.conf'],
        'power_state': {'mode': 'poweroff', 'timeout': 240, 'condition': True}
    }
    userdata_file = '{}/cloudinit_user_{}.yaml'.format(node_config['userdata_location'], vm.state['proxmox']['id'])
    not_really_a_file = io.StringIO(node_config['private_ssh_key'])
    private_key = paramiko.Ed25519Key.from_private_key(not_really_a_file)
    not_really_a_file.close()

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys() # TODO Server '195.154.87.154' not found in known_hosts if removed
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # TODO Is this good?
    ssh.connect(node_config['ip'], username=node_config['ssh_user'], pkey=private_key)
    scp = SCPClient(ssh.get_transport())

    fl = io.StringIO()
    fl.write('#cloud-config\n')
    yaml.dump(data, fl, default_flow_style=False)
    fl.seek(0)
    scp.putfo(fl, userdata_file)
    scp.close()
    fl.close()

    return True

def get_run_cmd(vm):
    # TODO, Add support for more then debian based OSes, perhaps read this from config files
    # TODO, we can add custom input here, between apt install and autoremove
    additional_run_cmd = vm.template.config['additional_run_cmd'] if 'additional_run_cmd' in vm.template.config else []

    pre = [
        'timedatectl set-timezone Europe/Oslo', # Remove hardcoded value
        'sed -i -e "s/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/" /etc/locale.gen',
        'sed -i -e "s/# nb_NO.UTF-8 UTF-8/nb_NO.UTF-8 UTF-8/" /etc/locale.gen',
        'dpkg-reconfigure --frontend=noninteractive locales',
        'update-locale LANG=en_US.UTF-8',
        'update-locale LANGUAGE=en_US:en',
        'touch /var/lib/cloud/instance/locale-check.skip',
        'DEBIAN_FRONTEND=noninteractive apt install -q -y software-properties-common qemu-guest-agent'
    ]

    late = [
        'apt autoremove -y',
        'rm /root/.ssh/authorized_keys',
        'echo "network: {config: disabled}" > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg'
    ]

    return pre + additional_run_cmd + late


def cleanup_cloudinit(pve_node_name, vm):
    node_config = vm.environment.config['proxmox']['nodes'][pve_node_name]
    userdata_file = '{}/cloudinit_user_{}.yaml'.format(node_config['userdata_location'], vm.state['proxmox']['id'])

    not_really_a_file = io.StringIO(node_config['private_ssh_key'])
    private_key = paramiko.Ed25519Key.from_private_key(not_really_a_file)
    not_really_a_file.close()

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys() # TODO Server '195.154.87.154' not found in known_hosts if removed
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # TODO Is this good?
    ssh.connect(node_config['ip'], username=node_config['ssh_user'], pkey=private_key)
    ssh.exec_command("rm {}".format(userdata_file))
    ssh.close()
    pass
