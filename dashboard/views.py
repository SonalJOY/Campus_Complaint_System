from django.shortcuts import render

def home(request):
    """
    Landing page view explaining system workflow and providing entry links.
    """
    return render(request, 'home.html')
