from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class InvalidStatusTransitionError(Exception):
    """
    Raised when an unauthorized or invalid complaint status transition is attempted.
    """
    pass


class Category(models.Model):
    """
    Categorization for campus complaints (e.g., Electrical, Plumbing, IT).
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the complaint category"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Scope and description of this maintenance category"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is available for new complaint submissions"
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Complaint(models.Model):
    """
    Core Complaint entity representing an infrastructure or maintenance ticket.
    Enforces a strict server-side state machine:
    SUBMITTED -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED
    """
    
    # Priority Choices
    PRIORITY_LOW = 'LOW'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_URGENT = 'URGENT'
    
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]
    
    # Status Choices
    STATUS_SUBMITTED = 'SUBMITTED'
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_RESOLVED = 'RESOLVED'
    STATUS_CLOSED = 'CLOSED'
    
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
    ]

    complaint_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Unique auto-generated ticket identifier (e.g., CMP-000123)"
    )
    title = models.CharField(
        max_length=200,
        help_text="Short summary of the issue"
    )
    description = models.TextField(
        help_text="Detailed description of the breakdown or maintenance required"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='complaints',
        help_text="Maintenance department/category"
    )
    location = models.CharField(
        max_length=255,
        help_text="Exact physical location (e.g., Block B, Room 302, Library 1st Floor)"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        help_text="Urgency level of the complaint"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED,
        help_text="Current state in the complaint lifecycle"
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='submitted_complaints',
        help_text="Student who created and reported the complaint"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_complaints',
        help_text="Maintenance staff member assigned to fix the issue"
    )
    image = models.ImageField(
        upload_to='complaints/%Y/%m/',
        blank=True,
        null=True,
        help_text="Optional photo of the damaged facility or equipment"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when complaint was submitted"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when complaint was last updated"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when staff marked the issue resolved"
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when student/admin closed the ticket"
    )

    class Meta:
        verbose_name = "Complaint"
        verbose_name_plural = "Complaints"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.complaint_id} - {self.title} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        """
        Auto-generates sequential, unique complaint_id (format: CMP-000123) if not present.
        """
        if not self.complaint_id:
            # We determine next sequential number inside transaction
            with transaction.atomic():
                last_complaint = Complaint.objects.select_for_update().order_by('-id').first()
                next_num = (last_complaint.id + 1) if last_complaint else 1
                candidate_id = f"CMP-{next_num:06d}"
                while Complaint.objects.filter(complaint_id=candidate_id).exists():
                    next_num += 1
                    candidate_id = f"CMP-{next_num:06d}"
                self.complaint_id = candidate_id
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def transition_to(self, new_status, user, remarks=None, assigned_to_user=None):
        """
        Strict server-side state machine transition engine:
        SUBMITTED -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED
        
        Rules:
        1. SUBMITTED -> ASSIGNED: Only ADMIN can assign a complaint to a STAFF member.
        2. ASSIGNED -> IN_PROGRESS: Only the assigned STAFF member can start work.
        3. IN_PROGRESS -> RESOLVED: Only the assigned STAFF member can resolve (remarks required).
        4. RESOLVED -> CLOSED: Only submitting STUDENT or ADMIN can close.
        5. No other transitions are allowed.
        
        Every transition is recorded in ComplaintHistory.
        """
        if not user or not user.is_authenticated:
            raise InvalidStatusTransitionError("An authenticated user is required to perform a status transition.")

        user_role = getattr(getattr(user, 'profile', None), 'role', None)
        is_admin = user.is_superuser or user_role == 'ADMIN'
        old_status = self.status

        # 1. Transition: SUBMITTED -> ASSIGNED
        if old_status == self.STATUS_SUBMITTED and new_status == self.STATUS_ASSIGNED:
            if not is_admin:
                raise InvalidStatusTransitionError("Only administrators can assign complaints to maintenance staff.")
            
            target_staff = assigned_to_user or self.assigned_to
            if not target_staff:
                raise InvalidStatusTransitionError("A staff member must be specified to assign this complaint.")
            
            target_role = getattr(getattr(target_staff, 'profile', None), 'role', None)
            if target_role != 'STAFF' and not target_staff.is_superuser:
                raise InvalidStatusTransitionError("Complaints can only be assigned to users with the STAFF role.")
            
            self.assigned_to = target_staff

        # 2. Transition: ASSIGNED -> IN_PROGRESS
        elif old_status == self.STATUS_ASSIGNED and new_status == self.STATUS_IN_PROGRESS:
            if user != self.assigned_to:
                raise InvalidStatusTransitionError("Only the assigned staff member can change status to IN_PROGRESS.")

        # 3. Transition: IN_PROGRESS -> RESOLVED
        elif old_status == self.STATUS_IN_PROGRESS and new_status == self.STATUS_RESOLVED:
            if user != self.assigned_to:
                raise InvalidStatusTransitionError("Only the assigned staff member can mark this complaint as RESOLVED.")
            
            if not remarks or not remarks.strip():
                raise InvalidStatusTransitionError("Resolution remarks are required when marking a complaint as RESOLVED.")
            
            self.resolved_at = timezone.now()

        # 4. Transition: RESOLVED -> CLOSED
        elif old_status == self.STATUS_RESOLVED and new_status == self.STATUS_CLOSED:
            if user != self.submitted_by and not is_admin:
                raise InvalidStatusTransitionError("Only the student who submitted this complaint (or an administrator) can close it.")
            
            self.closed_at = timezone.now()

        # Disallow any other transition
        else:
            raise InvalidStatusTransitionError(
                f"Invalid status transition from '{old_status}' to '{new_status}'. "
                f"Valid lifecycle path: SUBMITTED -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED."
            )

        # Atomic commit of state update and history log
        with transaction.atomic():
            self.status = new_status
            self.save()
            ComplaintHistory.objects.create(
                complaint=self,
                old_status=old_status,
                new_status=new_status,
                changed_by=user,
                remarks=remarks.strip() if remarks else ""
            )


class ComplaintHistory(models.Model):
    """
    Immutable audit log entry recording every complaint status change,
    who performed the change, timestamp, and optional/required remarks.
    """
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='history',
        help_text="Parent complaint ticket"
    )
    old_status = models.CharField(
        max_length=20,
        choices=Complaint.STATUS_CHOICES,
        help_text="Status before transition"
    )
    new_status = models.CharField(
        max_length=20,
        choices=Complaint.STATUS_CHOICES,
        help_text="Status after transition"
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaint_status_changes',
        help_text="User who initiated this status transition"
    )
    remarks = models.TextField(
        blank=True,
        null=True,
        help_text="Action notes or required resolution explanation"
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Exact timestamp of the status transition"
    )

    class Meta:
        verbose_name = "Complaint History"
        verbose_name_plural = "Complaint Histories"
        ordering = ['-changed_at']

    def __str__(self):
        changer = self.changed_by.username if self.changed_by else "System"
        return f"{self.complaint.complaint_id}: {self.old_status} -> {self.new_status} by {changer}"
