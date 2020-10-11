from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from jobs.models import Job

import json

# Create your views here.
def jobs(request, task, status):
    if request.method == "GET":
        data = []
        job = Job.objects.filter(task=task, status=status).first()
        if job is not None:
            data.append({
            "id": job.pk,
            "task": job.task,
            "status": job.status,
            "job": job.job
            })
        return JsonResponse(data, safe=False)

@csrf_exempt
def job(request, id):
    if request.method == "GET":
        data = []
        job = Job.objects.get(pk=id)
        if job is not None:
            data.append({
            "id": job.pk,
            "task": job.task,
            "status": job.status,
            "job": job.job
            })
        return JsonResponse(data, safe=False)
    elif request.method == "PATCH":
        job = Job.objects.get(pk=id)
        body = json.loads(request.body)
        if 'status' in body:
            job.status = body['status']
        job.save()
        return JsonResponse({
            "id": job.pk,
            "task": job.task,
            "status": job.status,
            "job": job.job
        }, safe=False)
