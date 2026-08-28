from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q, Count
from django.utils import timezone

from accounts.decorators import student_required, staff_required, admin_required
from complaints.models import Complaint, Category, ComplaintHistory, InvalidStatusTransitionError
from complaints.forms import (
    AdminComplaintManageForm,
    AdminForceCloseForm,
    StaffProgressForm,
    StaffResolutionForm,
)
from .forms import CategoryForm


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


# ==============================================================================
# STAFF MODULE VIEWS
# ==============================================================================

@staff_required
def staff_dashboard(request):
    """
    Maintenance Staff Portal dashboard.
    Displays metrics and work orders strictly assigned to the logged-in staff technician.
    """
    assigned_complaints = Complaint.objects.filter(assigned_to=request.user)

    total_assigned_count = assigned_complaints.count()
    pending_assigned_count = assigned_complaints.filter(status=Complaint.STATUS_ASSIGNED).count()
    in_progress_count = assigned_complaints.filter(status=Complaint.STATUS_IN_PROGRESS).count()
    resolved_count = assigned_complaints.filter(status=Complaint.STATUS_RESOLVED).count()
    closed_count = assigned_complaints.filter(status=Complaint.STATUS_CLOSED).count()
    high_priority_count = assigned_complaints.filter(
        priority__in=[Complaint.PRIORITY_HIGH, Complaint.PRIORITY_URGENT],
        status__in=[Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS]
    ).count()

    # Active tasks requiring technician action
    active_tasks = assigned_complaints.filter(
        status__in=[Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS]
    ).select_related('category', 'submitted_by').order_by(
        models.Case(
            models.When(priority=Complaint.PRIORITY_URGENT, then=models.Value(1)),
            models.When(priority=Complaint.PRIORITY_HIGH, then=models.Value(2)),
            models.When(priority=Complaint.PRIORITY_MEDIUM, then=models.Value(3)),
            default=models.Value(4),
            output_field=models.IntegerField(),
        ),
        '-created_at'
    )[:8]

    # Recently resolved work orders
    recent_resolved = assigned_complaints.filter(
        status__in=[Complaint.STATUS_RESOLVED, Complaint.STATUS_CLOSED]
    ).select_related('category', 'submitted_by').order_by('-resolved_at', '-updated_at')[:5]

    context = {
        'total_assigned_count': total_assigned_count,
        'pending_assigned_count': pending_assigned_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'high_priority_count': high_priority_count,
        'active_tasks': active_tasks,
        'recent_resolved': recent_resolved,
    }
    return render(request, 'dashboard/staff_dashboard.html', context)


@staff_required
def staff_complaint_list(request):
    """
    Searchable and filterable task registry for maintenance technicians.
    Strictly scoped to complaints where assigned_to == request.user.
    Includes dedicated tabs for Active Work Orders vs Previously Resolved History.
    """
    assigned_qs = Complaint.objects.filter(assigned_to=request.user).select_related('category', 'submitted_by').order_by('-created_at')

    # Tab handling: active (default) vs resolved vs all
    tab = request.GET.get('tab', 'active').strip()

    # Total counts for tab headers
    active_count = assigned_qs.filter(status__in=[Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS]).count()
    resolved_count = assigned_qs.filter(status__in=[Complaint.STATUS_RESOLVED, Complaint.STATUS_CLOSED]).count()
    all_count = assigned_qs.count()

    if tab == 'resolved':
        complaints_qs = assigned_qs.filter(status__in=[Complaint.STATUS_RESOLVED, Complaint.STATUS_CLOSED])
    elif tab == 'all':
        complaints_qs = assigned_qs
    else:  # 'active'
        complaints_qs = assigned_qs.filter(status__in=[Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS])

    # Search Query
    query = request.GET.get('q', '').strip()
    if query:
        complaints_qs = complaints_qs.filter(
            Q(complaint_id__icontains=query) |
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(location__icontains=query) |
            Q(submitted_by__username__icontains=query) |
            Q(submitted_by__first_name__icontains=query) |
            Q(submitted_by__last_name__icontains=query)
        )

    # Status Filter
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        complaints_qs = complaints_qs.filter(status=status_filter)

    # Priority Filter
    priority_filter = request.GET.get('priority', '').strip()
    if priority_filter:
        complaints_qs = complaints_qs.filter(priority=priority_filter)

    # Category Filter
    category_filter = request.GET.get('category', '').strip()
    if category_filter and category_filter.isdigit():
        complaints_qs = complaints_qs.filter(category_id=int(category_filter))

    # Pagination: 10 per page
    paginator = Paginator(complaints_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all().order_by('name')
    active_filters_count = sum(1 for v in [status_filter, priority_filter, category_filter] if v)

    context = {
        'page_obj': page_obj,
        'complaints': page_obj.object_list,
        'categories': categories,
        'query': query,
        'tab': tab,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'status_choices': Complaint.STATUS_CHOICES,
        'priority_choices': Complaint.PRIORITY_CHOICES,
        'total_count': complaints_qs.count(),
        'active_count': active_count,
        'resolved_count': resolved_count,
        'all_count': all_count,
        'active_filters_count': active_filters_count,
    }
    return render(request, 'dashboard/staff_complaint_list.html', context)


@staff_required
def staff_complaint_detail(request, complaint_id):
    """
    Staff detail view for an assigned work order.
    Strictly scoped to assigned_to=request.user (returns 404 for unauthorized complaints).
    Displays submitter info, photo proof, audit history, and transition forms.
    """
    complaint = get_object_or_404(
        Complaint.objects.select_related('category', 'submitted_by__profile'),
        complaint_id=complaint_id,
        assigned_to=request.user
    )

    history = complaint.history.all().order_by('-changed_at').select_related('changed_by__profile')
    progress_form = StaffProgressForm()
    resolve_form = StaffResolutionForm()

    context = {
        'complaint': complaint,
        'history': history,
        'progress_form': progress_form,
        'resolve_form': resolve_form,
    }
    return render(request, 'dashboard/staff_complaint_detail.html', context)


@staff_required
def staff_complaint_start_work(request, complaint_id):
    """
    Allows the assigned technician to start work on a task: ASSIGNED -> IN_PROGRESS.
    Strictly scoped to assigned_to=request.user.
    """
    complaint = get_object_or_404(
        Complaint,
        complaint_id=complaint_id,
        assigned_to=request.user
    )

    if request.method == 'POST':
        if complaint.status != Complaint.STATUS_ASSIGNED:
            messages.error(
                request,
                f"Complaint #{complaint.complaint_id} is in status '{complaint.get_status_display()}'. "
                f"Only ASSIGNED complaints can be transitioned to IN_PROGRESS."
            )
            return redirect('dashboard:staff_complaint_detail', complaint_id=complaint.complaint_id)

        remarks = request.POST.get('remarks', '').strip() or "Technician began repair work and diagnostics."

        try:
            complaint.transition_to(
                new_status=Complaint.STATUS_IN_PROGRESS,
                user=request.user,
                remarks=remarks
            )
            messages.success(
                request,
                f"Work started on Complaint #{complaint.complaint_id}. Status updated to IN_PROGRESS."
            )
        except InvalidStatusTransitionError as e:
            messages.error(request, f"Unable to start work: {e}")

    return redirect('dashboard:staff_complaint_detail', complaint_id=complaint.complaint_id)


@staff_required
def staff_complaint_resolve(request, complaint_id):
    """
    Allows the assigned technician to mark a task as resolved: IN_PROGRESS -> RESOLVED.
    Strictly requires non-empty resolution remarks and records resolved_at timestamp.
    Strictly scoped to assigned_to=request.user.
    """
    complaint = get_object_or_404(
        Complaint,
        complaint_id=complaint_id,
        assigned_to=request.user
    )

    if request.method == 'POST':
        if complaint.status != Complaint.STATUS_IN_PROGRESS:
            messages.error(
                request,
                f"Complaint #{complaint.complaint_id} is in status '{complaint.get_status_display()}'. "
                f"Only IN_PROGRESS complaints can be marked as RESOLVED."
            )
            return redirect('dashboard:staff_complaint_detail', complaint_id=complaint.complaint_id)

        form = StaffResolutionForm(request.POST)
        if form.is_valid():
            remarks = form.cleaned_data['remarks'].strip()
            try:
                complaint.transition_to(
                    new_status=Complaint.STATUS_RESOLVED,
                    user=request.user,
                    remarks=remarks
                )
                messages.success(
                    request,
                    f"Complaint #{complaint.complaint_id} has been marked as RESOLVED. "
                    f"Submitting student and administration have been notified for closure verification."
                )
            except InvalidStatusTransitionError as e:
                messages.error(request, f"Unable to resolve complaint: {e}")
        else:
            messages.error(
                request,
                "Mandatory resolution remarks are required. Please describe the maintenance work done to resolve the issue."
            )

    return redirect('dashboard:staff_complaint_detail', complaint_id=complaint.complaint_id)



# ==============================================================================
# ADMIN MODULE VIEWS
# ==============================================================================

@admin_required
def admin_dashboard(request):
    """
    Admin operations command center displaying key metrics, unassigned complaint queue,
    urgent tickets needing immediate triage, category breakdown, and maintenance team load.
    """
    all_complaints = Complaint.objects.all()

    total_count = all_complaints.count()
    submitted_count = all_complaints.filter(status=Complaint.STATUS_SUBMITTED).count()
    in_progress_count = all_complaints.filter(status=Complaint.STATUS_IN_PROGRESS).count()
    resolved_count = all_complaints.filter(status=Complaint.STATUS_RESOLVED).count()
    high_priority_count = all_complaints.filter(
        priority__in=[Complaint.PRIORITY_HIGH, Complaint.PRIORITY_URGENT],
        status__in=[Complaint.STATUS_SUBMITTED, Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS]
    ).count()
    closed_count = all_complaints.filter(status=Complaint.STATUS_CLOSED).count()

    # Unassigned complaints requiring triage (New SUBMITTED tickets)
    unassigned_complaints = all_complaints.filter(
        status=Complaint.STATUS_SUBMITTED
    ).select_related('category', 'submitted_by').order_by('-created_at')[:6]

    # Urgent & High Priority tickets currently active
    urgent_complaints = all_complaints.filter(
        priority__in=[Complaint.PRIORITY_HIGH, Complaint.PRIORITY_URGENT],
        status__in=[Complaint.STATUS_SUBMITTED, Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS]
    ).select_related('category', 'submitted_by', 'assigned_to').order_by('-created_at')[:6]

    # Category breakdown stats
    categories_stats = Category.objects.annotate(
        complaint_count=Count('complaints')
    ).order_by('-complaint_count')[:6]

    # Maintenance staff overview
    staff_members = User.objects.filter(
        profile__role='STAFF',
        is_active=True
    ).annotate(
        active_tasks=Count(
            'assigned_complaints',
            filter=Q(assigned_complaints__status__in=[Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS])
        )
    ).order_by('first_name', 'username')

    context = {
        'total_count': total_count,
        'submitted_count': submitted_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'high_priority_count': high_priority_count,
        'closed_count': closed_count,
        'unassigned_complaints': unassigned_complaints,
        'urgent_complaints': urgent_complaints,
        'categories_stats': categories_stats,
        'staff_members': staff_members,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@admin_required
def admin_complaint_list(request):
    """
    Searchable and filterable master list of all campus complaints for administrators.
    Supports filtering by status, priority, category, and assigned staff member.
    """
    complaints_qs = Complaint.objects.all().select_related('category', 'submitted_by', 'assigned_to').order_by('-created_at')

    # Search Query
    query = request.GET.get('q', '').strip()
    if query:
        complaints_qs = complaints_qs.filter(
            Q(complaint_id__icontains=query) |
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(location__icontains=query) |
            Q(submitted_by__username__icontains=query) |
            Q(submitted_by__first_name__icontains=query) |
            Q(submitted_by__last_name__icontains=query)
        )

    # Status Filter
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        complaints_qs = complaints_qs.filter(status=status_filter)

    # Priority Filter
    priority_filter = request.GET.get('priority', '').strip()
    if priority_filter:
        complaints_qs = complaints_qs.filter(priority=priority_filter)

    # Category Filter
    category_filter = request.GET.get('category', '').strip()
    if category_filter and category_filter.isdigit():
        complaints_qs = complaints_qs.filter(category_id=int(category_filter))

    # Assigned Staff Filter
    assigned_filter = request.GET.get('assigned_to', '').strip()
    if assigned_filter:
        if assigned_filter == 'unassigned':
            complaints_qs = complaints_qs.filter(assigned_to__isnull=True)
        elif assigned_filter.isdigit():
            complaints_qs = complaints_qs.filter(assigned_to_id=int(assigned_filter))

    # Pagination: 10 per page
    paginator = Paginator(complaints_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all().order_by('name')
    staff_users = User.objects.filter(profile__role='STAFF', is_active=True).order_by('first_name', 'username')

    active_filters_count = sum(1 for v in [status_filter, priority_filter, category_filter, assigned_filter] if v)

    context = {
        'page_obj': page_obj,
        'complaints': page_obj.object_list,
        'categories': categories,
        'staff_users': staff_users,
        'query': query,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'assigned_filter': assigned_filter,
        'status_choices': Complaint.STATUS_CHOICES,
        'priority_choices': Complaint.PRIORITY_CHOICES,
        'total_count': complaints_qs.count(),
        'active_filters_count': active_filters_count,
    }
    return render(request, 'dashboard/admin_complaint_list.html', context)


@admin_required
def admin_complaint_detail(request, complaint_id):
    """
    Comprehensive administrative complaint detail and assignment management view.
    Admins can review submitter details, photo proof, full audit history, and:
      - Assign a SUBMITTED ticket to staff (invokes state machine transition SUBMITTED -> ASSIGNED)
      - Reassign an ASSIGNED/IN_PROGRESS ticket to another staff member
      - Update priority and append operational instructions/remarks
      - Force close a RESOLVED ticket
    """
    complaint = get_object_or_404(
        Complaint.objects.select_related('category', 'submitted_by__profile', 'assigned_to__profile'),
        complaint_id=complaint_id
    )

    history = complaint.history.all().order_by('-changed_at').select_related('changed_by__profile')
    force_close_form = AdminForceCloseForm()

    if request.method == 'POST':
        manage_form = AdminComplaintManageForm(request.POST)
        if manage_form.is_valid():
            target_staff = manage_form.cleaned_data['assigned_to']
            new_priority = manage_form.cleaned_data['priority']
            remarks = manage_form.cleaned_data['remarks'].strip()

            try:
                # Case 1: Complaint is in SUBMITTED state
                if complaint.status == Complaint.STATUS_SUBMITTED:
                    if target_staff:
                        # Update priority first if altered
                        if complaint.priority != new_priority:
                            complaint.priority = new_priority
                            complaint.save(update_fields=['priority', 'updated_at'])

                        # State machine transition to ASSIGNED
                        complaint.transition_to(
                            new_status=Complaint.STATUS_ASSIGNED,
                            user=request.user,
                            remarks=remarks or f"Assigned to {target_staff.get_full_name() or target_staff.username} by administrator.",
                            assigned_to_user=target_staff
                        )
                        messages.success(
                            request,
                            f"Complaint #{complaint.complaint_id} has been transitioned to ASSIGNED and assigned to "
                            f"{target_staff.get_full_name() or target_staff.username}."
                        )
                    else:
                        # Only updated priority or added note while still SUBMITTED
                        changed_notes = []
                        if complaint.priority != new_priority:
                            old_p = complaint.get_priority_display()
                            complaint.priority = new_priority
                            complaint.save(update_fields=['priority', 'updated_at'])
                            changed_notes.append(f"Priority changed from {old_p} to {complaint.get_priority_display()}")
                        if remarks:
                            changed_notes.append(f"Admin remarks: {remarks}")

                        if changed_notes:
                            ComplaintHistory.objects.create(
                                complaint=complaint,
                                old_status=complaint.status,
                                new_status=complaint.status,
                                changed_by=request.user,
                                remarks="; ".join(changed_notes)
                            )
                            messages.success(request, f"Complaint #{complaint.complaint_id} details updated.")

                # Case 2: Complaint is in ASSIGNED state
                elif complaint.status == Complaint.STATUS_ASSIGNED:
                    changed_notes = []
                    staff_changed = (target_staff != complaint.assigned_to)

                    if staff_changed and target_staff:
                        old_staff_str = complaint.assigned_to.get_full_name() or complaint.assigned_to.username if complaint.assigned_to else "None"
                        new_staff_str = target_staff.get_full_name() or target_staff.username
                        complaint.assigned_to = target_staff
                        changed_notes.append(f"Reassigned from {old_staff_str} to {new_staff_str}")

                    if complaint.priority != new_priority:
                        old_p = complaint.get_priority_display()
                        complaint.priority = new_priority
                        changed_notes.append(f"Priority changed from {old_p} to {complaint.get_priority_display()}")

                    if remarks:
                        changed_notes.append(f"Admin remarks: {remarks}")

                    if changed_notes:
                        complaint.save(update_fields=['assigned_to', 'priority', 'updated_at'])
                        ComplaintHistory.objects.create(
                            complaint=complaint,
                            old_status=complaint.status,
                            new_status=complaint.status,
                            changed_by=request.user,
                            remarks="; ".join(changed_notes)
                        )
                        messages.success(
                            request,
                            f"Complaint #{complaint.complaint_id} updated successfully ({'; '.join(changed_notes)})."
                        )
                    else:
                        messages.info(request, "No modifications were submitted.")

                # Case 3: Other states (IN_PROGRESS, RESOLVED, CLOSED)
                else:
                    changed_notes = []
                    if target_staff and target_staff != complaint.assigned_to:
                        old_staff_str = complaint.assigned_to.get_full_name() or complaint.assigned_to.username if complaint.assigned_to else "None"
                        new_staff_str = target_staff.get_full_name() or target_staff.username
                        complaint.assigned_to = target_staff
                        changed_notes.append(f"Reassigned from {old_staff_str} to {new_staff_str}")

                    if complaint.priority != new_priority:
                        old_p = complaint.get_priority_display()
                        complaint.priority = new_priority
                        changed_notes.append(f"Priority changed from {old_p} to {complaint.get_priority_display()}")

                    if remarks:
                        changed_notes.append(f"Admin remarks: {remarks}")

                    if changed_notes:
                        complaint.save(update_fields=['assigned_to', 'priority', 'updated_at'])
                        ComplaintHistory.objects.create(
                            complaint=complaint,
                            old_status=complaint.status,
                            new_status=complaint.status,
                            changed_by=request.user,
                            remarks="; ".join(changed_notes)
                        )
                        messages.success(request, f"Complaint #{complaint.complaint_id} updated.")

                return redirect('dashboard:admin_complaint_detail', complaint_id=complaint.complaint_id)

            except InvalidStatusTransitionError as e:
                messages.error(request, f"Assignment error: {e}")
    else:
        manage_form = AdminComplaintManageForm(initial={
            'assigned_to': complaint.assigned_to,
            'priority': complaint.priority,
        })

    context = {
        'complaint': complaint,
        'history': history,
        'manage_form': manage_form,
        'force_close_form': force_close_form,
    }
    return render(request, 'dashboard/admin_complaint_detail.html', context)


@admin_required
def admin_complaint_force_close(request, complaint_id):
    """
    Allows administrators to close a complaint (especially verified RESOLVED tickets).
    Invokes state transition RESOLVED -> CLOSED, recording administrator remarks.
    """
    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    if request.method == 'POST':
        remarks = request.POST.get('remarks', '').strip() or "Verified and closed by administrator."

        try:
            if complaint.status == Complaint.STATUS_RESOLVED:
                complaint.transition_to(
                    new_status=Complaint.STATUS_CLOSED,
                    user=request.user,
                    remarks=remarks
                )
                messages.success(
                    request,
                    f"Complaint #{complaint.complaint_id} has been verified and permanently CLOSED."
                )
            else:
                # Emergency direct closure
                old_status = complaint.status
                complaint.status = Complaint.STATUS_CLOSED
                complaint.closed_at = timezone.now()
                complaint.save(update_fields=['status', 'closed_at', 'updated_at'])
                ComplaintHistory.objects.create(
                    complaint=complaint,
                    old_status=old_status,
                    new_status=Complaint.STATUS_CLOSED,
                    changed_by=request.user,
                    remarks=f"Administrative Direct Closure from {old_status}: {remarks}"
                )
                messages.success(
                    request,
                    f"Complaint #{complaint.complaint_id} has been administratively CLOSED."
                )
        except InvalidStatusTransitionError as e:
            messages.error(request, f"Unable to close complaint: {e}")

    return redirect('dashboard:admin_complaint_detail', complaint_id=complaint.complaint_id)


# ==============================================================================
# CATEGORY MANAGEMENT (CRUD)
# ==============================================================================

@admin_required
def admin_category_list(request):
    """
    Displays all maintenance categories with complaint counts and active status.
    """
    categories = Category.objects.annotate(
        complaint_count=Count('complaints')
    ).order_by('name')

    return render(request, 'dashboard/admin_category_list.html', {
        'categories': categories,
        'total_count': categories.count(),
        'active_count': categories.filter(is_active=True).count(),
    })


@admin_required
def admin_category_create(request):
    """
    Create a new campus maintenance category.
    """
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Maintenance category '{category.name}' created successfully.")
            return redirect('dashboard:admin_category_list')
    else:
        form = CategoryForm()

    return render(request, 'dashboard/admin_category_form.html', {
        'form': form,
        'action_title': 'Add New Category',
        'is_create': True,
    })


@admin_required
def admin_category_edit(request, pk):
    """
    Edit an existing maintenance category.
    """
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Maintenance category '{cat.name}' updated successfully.")
            return redirect('dashboard:admin_category_list')
    else:
        form = CategoryForm(instance=category)

    return render(request, 'dashboard/admin_category_form.html', {
        'form': form,
        'category': category,
        'action_title': f"Edit Category: {category.name}",
        'is_create': False,
    })


@admin_required
def admin_category_toggle(request, pk):
    """
    Toggle active/inactive status of a category.
    """
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.is_active = not category.is_active
        category.save(update_fields=['is_active'])
        status_word = "ACTIVATED (available for new complaints)" if category.is_active else "DEACTIVATED (hidden from submission form)"
        messages.success(request, f"Category '{category.name}' has been {status_word}.")
    return redirect('dashboard:admin_category_list')


# ==============================================================================
# USER MANAGEMENT (DIRECTORY & STATUS TOGGLE)
# ==============================================================================

@admin_required
def admin_user_list(request):
    """
    Campus user directory for administrators to view students, staff, and admins,
    review contact details & complaint counts, and activate/deactivate accounts.
    """
    users_qs = User.objects.select_related('profile').prefetch_related(
        'submitted_complaints', 'assigned_complaints'
    ).order_by('-date_joined')

    # Search Query
    query = request.GET.get('q', '').strip()
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(profile__phone__icontains=query)
        )

    # Role Filter
    role_filter = request.GET.get('role', '').strip()
    if role_filter in ['STUDENT', 'STAFF', 'ADMIN']:
        users_qs = users_qs.filter(profile__role=role_filter)

    # Active Status Filter
    status_filter = request.GET.get('status', '').strip()
    if status_filter == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        users_qs = users_qs.filter(is_active=False)

    # Pagination: 15 users per page
    paginator = Paginator(users_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Role counts for statistics chips
    student_count = User.objects.filter(profile__role='STUDENT').count()
    staff_count = User.objects.filter(profile__role='STAFF').count()
    admin_count = User.objects.filter(profile__role='ADMIN').count()

    context = {
        'page_obj': page_obj,
        'users': page_obj.object_list,
        'query': query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'total_count': users_qs.count(),
        'student_count': student_count,
        'staff_count': staff_count,
        'admin_count': admin_count,
    }
    return render(request, 'dashboard/admin_user_list.html', context)


@admin_required
def admin_user_toggle_status(request, user_id):
    """
    Toggle activation / deactivation of a user account.
    Self-deactivation is strictly prevented.
    """
    target_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        if target_user == request.user:
            messages.error(request, "Security constraint: You cannot deactivate your own administrator account.")
            return redirect('dashboard:admin_user_list')

        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=['is_active'])

        status_text = "ACTIVATED" if target_user.is_active else "DEACTIVATED"
        messages.success(request, f"User account '{target_user.username}' has been successfully {status_text}.")

    return redirect('dashboard:admin_user_list')
