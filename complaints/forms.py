from django import forms
from django.core.exceptions import ValidationError
from .models import Complaint, Category, ComplaintHistory


class ComplaintCreateForm(forms.ModelForm):
    """
    Form for students to report new campus complaints and upload optional photo proofs.
    """
    
    # Maximum allowed upload size: 5 Megabytes
    MAX_FILE_SIZE = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']

    class Meta:
        model = Complaint
        fields = ['title', 'category', 'location', 'priority', 'description', 'image']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Brief summary of the issue (e.g., AC not cooling in Lab 304)',
                'autofocus': 'autofocus'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exact physical location (e.g., Block B, 3rd Floor, Room 302)'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please provide detailed information regarding the malfunction, safety concerns, or equipment damage...'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/webp'
            }),
        }
        help_texts = {
            'image': 'Optional. Upload an image proof (JPG, PNG, or WEBP, max 5MB).',
            'priority': 'Indicate urgency level (URGENT should be reserved for safety hazards or total power/network outages).'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active categories
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['category'].empty_label = "-- Select Maintenance Category --"

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Validate file size
            if image.size > self.MAX_FILE_SIZE:
                raise ValidationError(f"Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.1f}MB")

            # Validate file extension
            ext = '.' + image.name.split('.')[-1].lower() if '.' in image.name else ''
            if ext not in self.ALLOWED_EXTENSIONS:
                raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: JPG, JPEG, PNG, WEBP.")

        return image

    def save(self, commit=True, submitted_by=None):
        instance = super().save(commit=False)
        if submitted_by:
            instance.submitted_by = submitted_by
        instance.status = Complaint.STATUS_SUBMITTED

        if commit:
            instance.save()
            # Log initial submission into history
            ComplaintHistory.objects.create(
                complaint=instance,
                old_status=Complaint.STATUS_SUBMITTED,
                new_status=Complaint.STATUS_SUBMITTED,
                changed_by=submitted_by,
                remarks="Ticket submitted by student."
            )
        return instance


class ComplaintCloseForm(forms.Form):
    """
    Form for students (or admins) to confirm resolution and close a complaint.
    """
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional feedback (e.g., Tested and verified that the issue is fully fixed. Thank you!)'
        }),
        help_text="Optional confirmation remarks before permanently closing the ticket."
    )


class AdminComplaintManageForm(forms.Form):
    """
    Form for administrators to assign/reassign staff, change priority, and provide instructions.
    """
    assigned_to = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="-- Select Maintenance Staff Member --",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    priority = forms.ChoiceField(
        choices=Complaint.PRIORITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional instructions or operational remarks for the assigned staff...'
        }),
        help_text="Recorded in the permanent audit history trail."
    )

    def __init__(self, *args, **kwargs):
        from django.contrib.auth.models import User
        super().__init__(*args, **kwargs)
        # Populate only active STAFF members
        self.fields['assigned_to'].queryset = User.objects.filter(
            profile__role='STAFF',
            is_active=True
        ).order_by('first_name', 'username')


class AdminForceCloseForm(forms.Form):
    """
    Form for administrators to force closure on a complaint.
    """
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Administrative reason or verification notes for closing this ticket...'
        }),
        help_text="Optional remarks recorded in the permanent audit trail."
    )


class StaffProgressForm(forms.Form):
    """
    Form for maintenance staff to transition a work order from ASSIGNED to IN_PROGRESS.
    """
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional operational notes (e.g. Inspecting breaker box, gathering replacement parts)...'
        }),
        help_text="Optional notes recorded in the permanent audit trail upon starting work."
    )


class StaffResolutionForm(forms.Form):
    """
    Form for maintenance staff to mark a complaint as RESOLVED.
    Mandatory resolution remarks detailing the fix are strictly required.
    """
    remarks = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Describe the specific repairs performed, components replaced, or testing conducted to resolve the breakdown...'
        }),
        help_text="Mandatory. Please provide a clear summary of the maintenance work completed."
    )


