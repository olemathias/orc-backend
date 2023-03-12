import yaml
import time
import re
import io
from scp import SCPClient
from paramiko import Ed25519Key, SSHClient, AutoAddPolicy

# TODO Change to ipaddress
from netaddr import IPNetwork


def find_pve_template(pve_node, template):
    pve_vm_templates = []
    for t in pve_node.qemu.get():
        print(t['name'])
        if re.match(
                template.vm_provider_state['pve_template'],
                t['name']) is not None:
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


def create_cloudinit_userdata(pve_node_name, instance):
    node_config = instance.platform.vm_provider_config['nodes'][pve_node_name]
    user = instance.template.vm_provider_state['user'] if 'user' in instance.template.vm_provider_state and instance.template.vm_provider_state['user'] is not None else 'orc-user'

    data = {
        'hostname': instance.name,
        'fqdn': '{}.{}'.format(
            instance.name,
            instance.platform.dns_forward_provider_config['domain']
        ),
        'user': user,
        'ssh_authorized_keys': instance.platform.vm_provider_config['ssh_authorized_keys'],
        'chpasswd': {
            'expire': False
        },
        'users': ['default'],
        'package_upgrade': True,
        'runcmd': get_run_cmd(instance),
        'bootcmd': ['echo "nameserver 1.1.1.1" > /etc/resolv.conf'],
        'power_state': {
            'mode': 'poweroff',
            'timeout': 240,
            'condition': True
        }
    }
    userdata_file = '{}/cloudinit_user_{}.yaml'.format(
        node_config['userdata_location'], instance.vm_provider_state['id'])
    not_really_a_file = io.StringIO(node_config['private_ssh_key'])
    private_key = Ed25519Key.from_private_key(not_really_a_file)
    not_really_a_file.close()

    ssh = SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(
        node_config['ip'],
        username=node_config['ssh_user'],
        pkey=private_key)
    scp = SCPClient(ssh.get_transport())

    fl = io.StringIO()
    fl.write('#cloud-config\n')
    yaml.dump(data, fl, default_flow_style=False)
    fl.seek(0)
    scp.putfo(fl, userdata_file)
    scp.close()
    fl.close()

    return True


def get_run_cmd(instance):
    # TODO, Add support for more than debian based OS, read this from config files
    # TODO, we can add custom input here, between apt install and autoremove
    additional_run_cmd = []
    if 'additional_run_cmd' in instance.template.vm_provider_state:
        additional_run_cmd += instance.template.vm_provider_state['additional_run_cmd']
    if 'userdata' in instance.config:
        additional_run_cmd += instance.config['userdata']

    pre = [
        'timedatectl set-timezone Europe/Oslo',  # Remove hardcoded value
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


def cleanup_cloudinit(pve_node_name, instance):
    node_config = instance.platform.vm_provider_config['nodes'][pve_node_name]
    userdata_file = '{}/cloudinit_user_{}.yaml'.format(
        node_config['userdata_location'], instance.vm_provider_state['id'])

    not_really_a_file = io.StringIO(node_config['private_ssh_key'])
    private_key = Ed25519Key.from_private_key(not_really_a_file)
    not_really_a_file.close()

    ssh = SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(
        node_config['ip'],
        username=node_config['ssh_user'],
        pkey=private_key)
    ssh.exec_command("rm {}".format(userdata_file))
    ssh.close()
    pass


def get_pve_node_and_vm(instance):
    if 'type' in instance.vm_provider_state and instance.vm_provider_state['type'] == 'pve' and 'id' in instance.vm_provider_state and instance.vm_provider_state['id'] is None:
        return None, None

    pve_vm = None
    pve_node = None
    for t in instance.platform.vm().cluster.resources.get(type='vm'):
        if t['type'] == 'qemu' and int(t['vmid']) == int(instance.vm_provider_state['id']):
            pve_node = instance.platform.vm().nodes(t['node'])
            pve_vm = pve_node.qemu(instance.vm_provider_state['id'])
            return pve_node, pve_vm
    return None, None


def create_qemu_vm(instance, pve_node_name="pve1"):
    pve_node = instance.platform.vm().nodes(pve_node_name)
    if pve_node is None:
        raise Exception('Failed to connect to pve node')
    pve_vm_template = find_pve_template(pve_node, instance.template)
    if pve_vm_template is None:
        raise Exception('VM Template not found, or more then one found')
    pve_vm_template_status = pve_vm_template.status().current.get()

    pve_vm_id = instance.platform.vm().cluster.nextid.get()
    instance.vm_provider_state['id'] = pve_vm_id
    instance.vm_provider_state['status'] = "provisioning"
    instance.vm_provider_state['template'] = {
        pve_vm_template_status['vmid']: pve_vm_template_status['name']}
    instance.vm_provider_state['node'] = pve_node_name
    instance.save()

    create_cloudinit_userdata(pve_node_name, instance)

    pve_clone_job_id = pve_vm_template.clone.post(
        newid=pve_vm_id,
        description="{}".format("just a test"),
        name=instance.name,
        full=1,
        target=pve_node_name
    )

    ip4 = instance.ipam_provider_state['ip_addresses'][0]['address']
    ip6 = instance.ipam_provider_state['ip_addresses'][1]['address']
    gw4 = IPNetwork(ip4)[1]
    gw6 = IPNetwork(ip6)[1]
    vlan_id = instance.network.get_vlan_id()

    wait_for_job(pve_node, pve_clone_job_id)
    new_vm = pve_node.qemu(pve_vm_id)
    new_vm.config.post(
        memory=int(
            instance.config['memory']) * 1024,
        cores=int(
            instance.config['cpu_cores']),
        net0="virtio,firewall={0},bridge={1},tag={2}".format(
            int(1),
            instance.platform.vm_provider_config['nodes'][pve_node_name]['vmbridge'],
            vlan_id),
        ipconfig0="gw={},gw6={},ip={},ip6={}".format(
            gw4,
            gw6,
            ip4,
            ip6),
        searchdomain=instance.platform.dns_forward_provider_config['domain'],
        cicustom='user={}/cloudinit_user_{}.yaml'.format(
            'local:snippets',
            pve_vm_id))
    new_vm.resize.put(
        disk='scsi0',
        size="{}G".format(instance.config['disks'][0]['size'])
    )
    wait_for_job(pve_node, new_vm.status.start.post())
    time.sleep(1)  # Just to make sure status is changed to running
    if True:
        new_vm.firewall.ipset.post(name='ipfilter-net0')
        new_vm.firewall.ipset(
            'ipfilter-net0').post(cidr="{}/32".format(str(IPNetwork(ip4).ip)))
        new_vm.firewall.ipset(
            'ipfilter-net0').post(cidr="{}/128".format(str(IPNetwork(ip6).ip)))
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

    instance.vm_provider_state['status'] = "provisioned"
    instance.save()

    cleanup_cloudinit(pve_node_name, instance)
    return True


def delete_qemu_vm(instance):
    if 'type' in instance.vm_provider_state and instance.vm_provider_state['type'] == 'pve' and 'id' in instance.vm_provider_state and instance.vm_provider_state['id'] is None:
        return False

    pve_node, pve_vm = get_pve_node_and_vm(instance)
    if pve_node is None or pve_vm is None:
        return False

    wait_for_job(pve_node, pve_vm.status.stop.post())
    wait_for_poweroff(pve_node, instance.vm_provider_state['id'])
    wait_for_job(pve_node, pve_vm.delete())
    return True
