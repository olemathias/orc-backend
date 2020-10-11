from django.contrib import admin

# Register your models here.
from .models import HostCluster, HostClusterNode, Vm

admin.site.register(HostCluster)
admin.site.register(HostClusterNode)
admin.site.register(Vm)
