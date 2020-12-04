from django_rq import job
from vm.models import Vm
import time

@job
def update_vm_job(id):
    vm = Vm.objects.get(id=id)
    vm.update_state()
    return True

@job
def delete_vm_job(id):
    vm = Vm.objects.get(id=id)
    vm.delete_vm()
    return True

@job
def run_awx_template_job(id, template_id, template_name):
    vm = Vm.objects.get(id=id)
    awx = vm.environment.awx()
    template = awx.get_job_template_by_id(template_id)
    job = template.launch(limit=vm.fqdn)
    time.sleep(1) # To make sure job is registered
    while job.status in ["waiting", "pending", "running"]:
        vm.refresh_from_db()
        if vm.state["awx_templates"][template_name]["status"] != job.status:
            vm.state["awx_templates"][template_name]["status"] = job.status
            vm.save()
        time.sleep(2)
    vm.refresh_from_db()
    if job.finished is None:
        vm.state["awx_templates"][template_name]["status"] = job.status
        vm.save()
        return False
    vm.state["awx_templates"][template_name]["status"] = job.status
    vm.state["awx_templates"][template_name]["finished"] = job.finished
    vm.state["awx_templates"][template_name]["elapsed_time"] = job.elapsed_time
    vm.save()
    vm.update_state()
    return True
