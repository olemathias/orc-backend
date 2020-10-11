from django.db import models
from ipam.models import Network

# Create your models here.

class HostCluster(models.Model):
    type = models.CharField(max_length=16)
    name = models.CharField(max_length=256)
    status = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class HostClusterNode(models.Model):
    host_cluster = models.ForeignKey(HostCluster, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    url = models.CharField(max_length=256)
    status = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Vm(models.Model):
    vm_id = models.IntegerField(null=True)
    host_cluster = models.ForeignKey(HostCluster, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    config = models.JSONField()
    status = models.CharField(max_length=64)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
