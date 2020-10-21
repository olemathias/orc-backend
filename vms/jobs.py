from django_rq import job

from vms.models import Vm

import time

@job
def update_vm_job(id):
    print(id)
    vm = Vm.objects.get(pk=int(id))
    vm.update_state()
    return True

@job
def delete_vm_job(id):
    print(id)
    vm = Vm.objects.get(pk=int(id))
    vm.delete_vm()
    return True

@job
def run_awx_template_job(id, template_id, template_name):
    vm = Vm.objects.get(pk=int(id))
    awx = vm.environment.awx()
    template = awx.get_job_template_by_id(template_id)
    job = template.launch(limit=vm.fqdn)
    time.sleep(1) # To make sure job is registered
    while job.status in ["waiting", "pending", "running"]:
        vm.state["awx_templates"][template_name]["status"] = job.status
        vm.save()
        time.sleep(5)
    if job.finished is None:
        vm.state["awx_templates"][template_name]["status"] = job.status
        vm.save()
        return False
    vm.state["awx_templates"][template_name]["status"] = job.status
    vm.state["awx_templates"][template_name]["finished"] = job.finished
    vm.state["awx_templates"][template_name]["elapsed_time"] = job.elapsed_time
    vm.save()
    return True
