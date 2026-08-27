from django.shortcuts import render
from accounts.decorators import student_required, staff_required, admin_required


def home(request):
    """
    Landing page view explaining system workflow and providing entry links.
    """
    return render(request, 'home.html')


@student_required
def student_dashboard(request):
    """
    Student dashboard placeholder (Phase 4 will build the full complaint portal).
    """
    return render(request, 'dashboard/student_dashboard.html')


@staff_required
def staff_dashboard(request):
    """
    Staff dashboard placeholder (Phase 5 will build the assigned tasks portal).
    """
    return render(request, 'dashboard/staff_dashboard.html')


@admin_required
def admin_dashboard(request):
    """
    Admin dashboard placeholder (Phase 6 will build the management portal).
    """
    return render(request, 'dashboard/admin_dashboard.html')
