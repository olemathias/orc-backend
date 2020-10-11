from django.db import models

# Create your models here.
class Job(models.Model):
    task = models.CharField(max_length=16)
    status = models.CharField(max_length=16)
    description = models.CharField(max_length=64)
    job = models.JSONField()

    def __str__(self):
        return self.description
