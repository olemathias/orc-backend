from django.http import JsonResponse

from jobs.models import Job

# Create your views here.
def get_jobs(request):
    job = Job.objects.filter(status="new").first()
    data = [{
    "id": job.pk,
    "task": job.task,
    "status": job.status,
    "job": job.job
    }]
    return JsonResponse(data, safe=False)
