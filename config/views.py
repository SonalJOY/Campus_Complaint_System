from django.shortcuts import render


def custom_403(request, exception=None):
    """
    Custom 403 Forbidden handler with friendly role-based access advice.
    """
    context = {
        'message': 'You do not have the required permissions to access this campus facility resource.',
    }
    return render(request, '403.html', context, status=403)


def custom_404(request, exception=None):
    """
    Custom 404 Not Found handler with return navigation.
    """
    context = {
        'message': 'The requested complaint, work order, or page could not be found.',
    }
    return render(request, '404.html', context, status=404)


def custom_500(request):
    """
    Custom 500 Server Error handler.
    """
    context = {
        'message': 'An internal server error occurred while processing your maintenance request.',
    }
    return render(request, '500.html', context, status=500)
