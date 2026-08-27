from django.shortcuts import render
from accounts.decorators import student_required, staff_required, admin_required
from complaints.models import Complaint


def home(request):
    """
    Landing page view explaining system workflow and providing entry links.
    """
    return render(request, 'home.html')


@student_required
def student_dashboard(request):
    """
    Student dashboard displaying real summary statistics (Total, Pending, In Progress, Resolved, Closed)
    and a table of recent complaints submitted by the logged-in student.
    """
    user_complaints = Complaint.objects.filter(submitted_by=request.user)

    total_count = user_complaints.count()
    pending_count = user_complaints.filter(
        status__in=[Complaint.STATUS_SUBMITTED, Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS]
    ).count()
    in_progress_count = user_complaints.filter(status=Complaint.STATUS_IN_PROGRESS).count()
    resolved_count = user_complaints.filter(status=Complaint.STATUS_RESOLVED).count()
    closed_count = user_complaints.filter(status=Complaint.STATUS_CLOSED).count()

    recent_complaints = user_complaints.select_related('category', 'assigned_to').order_by('-created_at')[:6]

    context = {
        'total_count': total_count,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'recent_complaints': recent_complaints,
    }
    return render(request, 'dashboard/student_dashboard.html', context)


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
