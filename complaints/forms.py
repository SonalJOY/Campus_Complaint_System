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
