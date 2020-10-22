from django.shortcuts import render

from ipam.models import Environment
from ipam.forms import EnvironmentForm

# Create your views here.
def index(request):
    return render(request, 'environment/index.html', {'environments': Environment.objects.all()})

def show(request, id):
    environment = Environment.objects.get(pk=id)
    return render(request, 'environment/show.html', {'environment': environment})

def edit(request, id):
    if request.method == "GET":
        environment = Environment.objects.get(pk=id)
        return render(request, 'environment/edit.html', {'environment': environment})
    elif request.method == "POST":
        pass
