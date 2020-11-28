from django.contrib import admin
from vm.models import Vm, VmTemplate, AWXTemplate

admin.site.register(Vm)
admin.site.register(VmTemplate)
admin.site.register(AWXTemplate)
