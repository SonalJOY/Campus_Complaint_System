from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from accounts.decorators import student_required
from .models import Complaint, Category, ComplaintHistory, InvalidStatusTransitionError
from .forms import ComplaintCreateForm, ComplaintCloseForm


@student_required
def student_complaint_create(request):
    """
    Allows a student to create and submit a new maintenance complaint.
    """
    if request.method == 'POST':
        form = ComplaintCreateForm(request.POST, request.FILES)
        if form.is_valid():
            complaint = form.save(commit=True, submitted_by=request.user)
            messages.success(
                request,
                f"Complaint #{complaint.complaint_id} ('{complaint.title}') has been successfully submitted! "
                f"Operations administration has been notified for assignment."
            )
            return redirect('complaints:student_complaint_detail', complaint_id=complaint.complaint_id)
    else:
        form = ComplaintCreateForm()

    return render(request, 'complaints/student_complaint_form.html', {
        'form': form,
        'categories': Category.objects.filter(is_active=True),
    })


@student_required
def student_complaint_list(request):
    """
    Displays filterable and searchable list of complaints submitted exclusively by the logged-in student.
    """
    complaints_qs = Complaint.objects.filter(submitted_by=request.user).select_related('category', 'assigned_to').order_by('-created_at')

    # Search query
    query = request.GET.get('q', '').strip()
    if query:
        complaints_qs = complaints_qs.filter(
            Q(complaint_id__icontains=query) |
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(location__icontains=query)
        )

    # Status filter
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        complaints_qs = complaints_qs.filter(status=status_filter)

    # Category filter
    category_filter = request.GET.get('category', '').strip()
    if category_filter and category_filter.isdigit():
        complaints_qs = complaints_qs.filter(category_id=int(category_filter))

    # Priority filter
    priority_filter = request.GET.get('priority', '').strip()
    if priority_filter:
        complaints_qs = complaints_qs.filter(priority=priority_filter)

    # Pagination: 8 per page
    paginator = Paginator(complaints_qs, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(is_active=True)

    return render(request, 'complaints/student_complaint_list.html', {
        'page_obj': page_obj,
        'complaints': page_obj.object_list,
        'categories': categories,
        'query': query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'priority_filter': priority_filter,
        'status_choices': Complaint.STATUS_CHOICES,
        'priority_choices': Complaint.PRIORITY_CHOICES,
        'total_count': complaints_qs.count(),
    })


@student_required
def student_complaint_detail(request, complaint_id):
    """
    Shows detailed view of a student's own complaint, including photo attachment,
    assigned staff metadata, full audit timeline, and closure button if resolved.
    """
    # Strictly scoped to request.user (returns 404 on others' complaints)
    complaint = get_object_or_404(
        Complaint.objects.select_related('category', 'submitted_by', 'assigned_to'),
        complaint_id=complaint_id,
        submitted_by=request.user
    )

    history = complaint.history.all().order_by('changed_at').select_related('changed_by')
    close_form = ComplaintCloseForm()

    return render(request, 'complaints/student_complaint_detail.html', {
        'complaint': complaint,
        'history': history,
        'close_form': close_form,
    })


@student_required
def student_complaint_close(request, complaint_id):
    """
    Handles student closure of a RESOLVED complaint (RESOLVED -> CLOSED transition).
    """
    complaint = get_object_or_404(
        Complaint,
        complaint_id=complaint_id,
        submitted_by=request.user
    )

    if request.method == 'POST':
        if complaint.status != Complaint.STATUS_RESOLVED:
            messages.error(
                request,
                f"Complaint #{complaint.complaint_id} is in status '{complaint.get_status_display()}'. "
                f"Only RESOLVED complaints can be closed by the student."
            )
            return redirect('complaints:student_complaint_detail', complaint_id=complaint.complaint_id)

        form = ComplaintCloseForm(request.POST)
        remarks = request.POST.get('remarks', '').strip() or "Verified and closed by student."

        try:
            complaint.transition_to(
                new_status=Complaint.STATUS_CLOSED,
                user=request.user,
                remarks=remarks
            )
            messages.success(
                request,
                f"Complaint #{complaint.complaint_id} has been officially verified and CLOSED. Thank you for your feedback!"
            )
        except InvalidStatusTransitionError as e:
            messages.error(request, f"Unable to close complaint: {e}")

    return redirect('complaints:student_complaint_detail', complaint_id=complaint.complaint_id)
