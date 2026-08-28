from django import forms
from complaints.models import Category


class CategoryForm(forms.ModelForm):
    """
    Form for administrators to create or edit maintenance categories.
    """
    class Meta:
        model = Category
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category Name (e.g. Electrical, HVAC, Carpentry)',
                'autofocus': 'autofocus'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Scope of maintenance services covered under this category...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        help_texts = {
            'is_active': 'Check to make this category available for student complaint submissions.'
        }
