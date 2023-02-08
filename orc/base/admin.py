from django.contrib import admin
from orc.base.models import Platform, Network, Instance, InstanceImage

admin.site.register(Platform)
admin.site.register(Network)
admin.site.register(Instance)
admin.site.register(InstanceImage)