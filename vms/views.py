from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings

from django.views.decorators.csrf import csrf_exempt

from vms.models import Vm
from ipam.models import Network, Environment
from vms.forms import VmForm

from vms.jobs import update_vm_job, delete_vm_job

from netaddr import *
import json

from django.template.defaulttags import register

@register.filter
def get_item(dictionary, key):
    if dictionary:
        return dictionary.get(key)
    return None

# Create your views here.
def index(request):
    return render(request, 'vms/index.html', {'vms': Vm.objects.all()})

def show(request, id):
    vm = Vm.objects.get(pk=id)
    return render(request, 'vms/show.html', {'vm': vm})

@csrf_exempt
def vm(request, id):
    vm = Vm.objects.get(pk=id)
    if request.method == "PATCH":
        body = json.loads(request.body)
        if 'state' in body:
            vm.state = {**vm.state, **body['state']}
        if 'config' in body:
            vm.config = {**vm.config, **body['config']}
        vm.save()

    return JsonResponse({
        "id": vm.pk,
        "environment_id": vm.environment.pk,
        "network_id": vm.network.id,
        "name": vm.name,
        "config": vm.config,
        "state": vm.state
    }, safe=False)

def create(request):
    if request.method == "GET":
        form = VmForm()
        return render(request, 'vms/create.html', {'form': form})
    elif request.method == "POST":

        environment = Environment.objects.get(pk=request.POST['environment'])
        network = Network.objects.get(pk=request.POST['network'])

        vm = Vm()
        vm.name = request.POST['name']
        vm.state = {}
        vm.environment = environment
        vm.network = network

        ipv4 = IPNetwork(network.get_next_ip()['ipv4'])
        ipv6 = IPNetwork(network.get_next_ip()['ipv6'])

        vm.config = {
            "name": vm.name,
            "os_template": request.POST['os_template'],
            "role": 1,
            "hw": {
                "memory": request.POST['memory'],
                "cpu_cores": request.POST['cpu_cores'],
                "os_disk": request.POST['os_disk'],
            },
            "net": {
                "vlan_id": network.vid(),
                "ipv4": {
                    "ip": str(ipv4.ip),
                    "prefixlen": ipv4.prefixlen,
                    "gw": str(ipv4[1])
                },
                "ipv6": {
                    "ip": str(ipv6.ip),
                    "prefixlen": ipv6.prefixlen,
                    "gw": str(ipv6[1])
                },
                "domain": environment.config['domain'],
                "firewall": True
            }
        }

        vm.config["awx_templates"] = {
            "ipa_install": {"id": 10, "name": "Install IPAClient", "trigger": {"after_state": ["netbox", "proxmox", "awx", "freeipa", "powerdns"]}},
            "docker_test": {"id": 12, "name": "Docker Test", "trigger": {"after_state": ["netbox", "proxmox", "awx", "freeipa", "powerdns"]}}
        }

        vm.save()
        vm.update_netbox()
        update_vm_job.delay(vm.pk)
        return redirect("/vms/")

def delete(request, id):
    vm = Vm.objects.get(pk=id)
    delete_vm_job.delay(vm.pk)
    return redirect("/vms".format(vm.pk))

def reboot(request, id):
    from vms.proxmox import restart_qemu_vm_job
    vm = Vm.objects.get(pk=id)
    restart_qemu_vm_job.delay(vm.pk)
    return redirect("/vms/{}".format(vm.pk))

def update_state(request, id):
    vm = Vm.objects.get(pk=id)
    update_vm_job.delay(vm.pk)
    return redirect("/vms/{}".format(vm.pk))

def run_awx_template(request, id, template_name):
    vm = Vm.objects.get(pk=id)
    if template_name not in vm.config['awx_templates']:
        return redirect("/vms/{}".format(vm.pk)) ## TODO Add Flash
    template = vm.config['awx_templates'][template_name]
    from vms.jobs import run_awx_template_job
    run_awx_template_job.delay(vm.pk, template['id'], template_name)
    return redirect("/vms/{}".format(vm.pk))
