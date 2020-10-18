from django import forms
from ipam.models import Network, Environment
from django.conf import settings
from .models import Vm

class VmForm(forms.Form):
    name = forms.CharField()
    environment = forms.ModelChoiceField(queryset=Environment.objects.all(), empty_label=None)
    network = forms.ModelChoiceField(queryset=Network.objects.all(), empty_label=None)
    os_template = forms.ChoiceField(label="OS Template", choices=[["debian10", "Debian 10 - Managed"],["ubuntu2004", "Ubuntu 20.04 - Managed"]])
    #role = forms.ChoiceField(choices=map(lambda x : [x.id, x.name], nb.dcim.device_roles.filter(vm_role=True)))
    cpu_cores = forms.ChoiceField(choices=[[2, 2],[4, 4],[6, 6],[8, 8]])
    memory = forms.IntegerField(help_text="In GB", initial=4)
    os_disk = forms.IntegerField(help_text="In GB.", initial=32)
