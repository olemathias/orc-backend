from django import forms
from ipam.models import Network, Environment
from django.conf import settings

class EnvironmentForm(forms.ModelForm):

    class Meta:
        model = Environment
        fields = ['name']

    def __init__(self, *args, instance=None, **kwargs):
        super(EnvironmentForm, self).__init__(*args, instance=instance, **kwargs)
        if instance:
            for state_name, state in instance.config.items():
                if state_name in ['netbox', 'powerdns', 'awx', 'freeipa', 'proxmox']:
                    for key, value in state.items():
                        if key in ['token', 'key', 'password', 'token_value']:
                            self.fields[f'{state_name}_{key}'] = forms.CharField(initial=value, widget=forms.PasswordInput)
                        else:
                            self.fields[f'{state_name}_{key}'] = forms.CharField(initial=value)
