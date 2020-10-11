from django import forms
from ipam.models import Network
from .models import Vm, HostCluster

class VmForm(forms.Form):
    name = forms.CharField()
    domain = forms.ChoiceField(choices=[["gathering.systems", "gathering.systems"],["gathering.org", "gathering.org"]])
    host_cluster = forms.ModelChoiceField(queryset=HostCluster.objects.all(), empty_label=None)
    network = forms.ModelChoiceField(queryset=Network.objects.all(), empty_label=None)
    os_template = forms.ChoiceField(label="OS Template", choices=[["debian10", "Debian 10 - Managed"],["ubuntu2004", "Ubuntu 20.04 - Managed"]])
    cpu_cores = forms.ChoiceField(choices=[[2, 2],[4, 4],[6, 6],[8, 8]])
    memory = forms.IntegerField(help_text="In GB. Max 32", max_value=32, initial=4)
    os_disk = forms.IntegerField(help_text="In GB.", initial=32)
