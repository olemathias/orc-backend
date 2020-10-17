from django.contrib import admin

# Register your models here.
from .models import Network, Environment

admin.site.register(Network)
admin.site.register(Environment)
