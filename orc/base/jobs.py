from django_rq import job
from orc.base.models import Instance
from orc.base.providers import proxmox
from orc.base.providers import netbox
from orc.base.providers import pdns
from orc.base.providers import freeipa


@job("default", timeout=900)  # 15 min
def create_instance_job(instance_id):
    instance = Instance.objects.get(id=instance_id)
    platform = instance.platform
    # template = instance.template

    # DNS Forward Provider
    if platform.dns_forward_provider_config['type'] == 'pdns':
        if instance.dns_forward_provider_state is None or 'type' not in instance.dns_forward_provider_state:
            instance.dns_forward_provider_state = {'type': 'pdns'}
            pdns.create_forward_instance(instance)

    # DNS Reverse Provider
    if platform.dns_reverse_provider_config['type'] == 'pdns':
        if instance.dns_reverse_provider_state is None or 'type' not in instance.dns_reverse_provider_state:
            instance.dns_reverse_provider_state = {'type': 'pdns'}
            pdns.create_reverse_instance(instance)

    # Identity Management Provider
    if platform.identity_management_provider_config['type'] == 'freeipa':
        if instance.identity_management_provider_state is None or 'type' not in instance.identity_management_provider_state:
            instance.identity_management_provider_state = {'type': 'freeipa'}
            freeipa.create_host(instance)

    # VM Provider
    if platform.vm_provider_config['type'] == 'pve':
        if instance.vm_provider_state is None or 'type' not in instance.vm_provider_state:
            instance.vm_provider_state = {'type': 'pve'}
            proxmox.create_qemu_vm(instance)

    return True


@job("default", timeout=300)  # 5 min
def delete_instance_job(instance_id):
    instance = Instance.objects.get(id=instance_id)
    platform = instance.platform

    # VM Provider
    if platform.vm_provider_config['type'] == 'pve':
        if instance.vm_provider_state is not None and 'type' in instance.vm_provider_state and instance.vm_provider_state['type'] == 'pve':
            proxmox.delete_qemu_vm(instance)
            instance.vm_provider_state = None
            instance.save()

    # Identity Management Provider
    if platform.identity_management_provider_config['type'] == 'freeipa':
        if instance.identity_management_provider_state is not None and 'type' in instance.identity_management_provider_state and instance.identity_management_provider_state['type'] == 'freeipa':
            freeipa.delete_host(instance)
            instance.identity_management_provider_state = None
            instance.save()

    # DNS Forward Provider
    if platform.dns_forward_provider_config['type'] == 'pdns':
        if instance.dns_forward_provider_state is not None and 'type' in instance.dns_forward_provider_state and instance.dns_forward_provider_state['type'] == 'pdns':
            pdns.delete_forward_instance(instance)
            instance.dns_forward_provider_state = None
            instance.save()

    # DNS Reverse Provider
    if platform.dns_reverse_provider_config['type'] == 'pdns':
        if instance.dns_reverse_provider_state is not None and 'type' in instance.dns_reverse_provider_state and instance.dns_reverse_provider_state['type'] == 'pdns':
            pdns.delete_reverse_instance(instance)
            instance.dns_reverse_provider_state = None
            instance.save()

    # IPAM Provider
    if platform.ipam_provider_config['type'] == 'netbox':
        if instance.ipam_provider_state is not None and 'type' in instance.ipam_provider_state and instance.ipam_provider_state['type'] == 'netbox':
            netbox.delete_vm(instance)
            instance.ipam_provider_state = None
            instance.save()

    # TODO Check to make sure nothing is still left in all providers
    instance.delete()

    return True
