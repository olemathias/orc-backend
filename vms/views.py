from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings


from vms.models import Vm, HostCluster
from ipam.models import Network
from jobs.models import Job
from .forms import VmForm

from netaddr import *
from proxmoxer import ProxmoxAPI

# Create your views here.
def index(request):
    return render(request, 'vms/index.html')

def create(request):
    if request.method == "GET":
        form = VmForm()
        return render(request, 'vms/create.html', {'form': form})
    elif request.method == "POST":

        host_cluster = HostCluster.objects.get(pk=request.POST['host_cluster'])
        network = Network.objects.get(pk=request.POST['network'])

        vm = Vm()
        vm.name = request.POST['name']
        vm.vm_id = None
        vm.host_cluster = host_cluster
        vm.network = network
        vm.status = "active"

        ipv4 = IPNetwork(network.get_next_ip()['ipv4'])
        ipv6 = IPNetwork(network.get_next_ip()['ipv6'])

        vm.config = {
            "name": vm.name,
            "os_template": request.POST['os_template'],
            "hw": {
                "memory": request.POST['memory'],
                "cpu_cores": request.POST['cpu_cores'],
                "os_disk": request.POST['os_disk'],
            },
            "config": {
                "ipv4": {
                    "ip": str(ipv4.ip),
                    "netmask": ipv4.prefixlen,
                    "gw": str(ipv4[1])
                },
                "ipv6": {
                    "ip": str(ipv6.ip),
                    "netmask": ipv6.prefixlen,
                    "gw": str(ipv6[1])
                },
                "domain": request.POST['domain']
            }
        }

        vm.save()

        job = Job(task="create_vm", status="new")
        job.description = "Create VM {} in {}".format(vm.name, vm.host_cluster)
        job.job = vm.config
        job.save()
        return HttpResponse(request.POST['name'])
