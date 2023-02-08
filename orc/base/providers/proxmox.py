import yaml
import time
import re

import io
import paramiko
from scp import SCPClient

def find_pve_template(pve_node, template):
    pve_vm_templates = []
    for t in pve_node.qemu.get():
        print(t['name'])
        if re.match(template.config['pve_template'], t['name']) is not None:
            pve_vm_templates.append(pve_node.qemu(t['vmid']))

    # Only return if we have one match
    if len(pve_vm_templates) == 1:
        return pve_vm_templates[0]
    return None

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
    node_config = vm.platform.config['proxmox']['nodes'][pve_node_name]

    user = vm.template.config['user'] if 'user' in vm.template.config and vm.template.config['user'] is not None else 'orc-user'

    data = {
        'hostname': vm.name,
        'fqdn': '{}.{}'.format(vm.name, vm.platform.config['domain']),
        'user': user,
        'ssh_authorized_keys': vm.platform.config['proxmox']['ssh_authorized_keys'],
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
    # TODO, Add support for more than debian based OS, read this from config files
    # TODO, we can add custom input here, between apt install and autoremove
    additional_run_cmd = []
    if 'additional_run_cmd' in vm.template.config:
        additional_run_cmd += vm.template.config['additional_run_cmd']
    if 'userdata' in vm.config:
        additional_run_cmd += vm.config['userdata']

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
    node_config = vm.platform.config['proxmox']['nodes'][pve_node_name]
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
