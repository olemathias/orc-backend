from django_rq import job
from orc.base.models import Instance


@job
def restart_qemu_vm_job(instance_id):
    instance = Instance.objects.get(id=instance_id)
    if 'proxmox' not in instance.state or 'id' not in instance.state[
            'proxmox'] or instance.state['proxmox']['id'] is None:
        return False

    pve_node, pve_vm = instance.get_pve_node_and_vm()
    if pve_node is None or pve_vm is None:
        return False

    pve_vm.status.reboot.post()
    return True
