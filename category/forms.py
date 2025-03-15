from django import forms
from .models import Category

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category_name', 'description']
        widgets = {
            'category_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name',
                'minlength': '2',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category description',
                'rows': 3,
                'required': True
            }),
            
        }

    def clean_category_name(self):
        name = self.cleaned_data.get('category_name', '').strip()
        if not name:
            raise forms.ValidationError("Category name is required")
        if len(name) < 2:
            raise forms.ValidationError("Category name must be at least 2 characters long")
        
        # Case-insensitive uniqueness check
        if Category.objects.filter(category_name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A category with this name already exists")
        
        # Check for special characters
        if not all(char.isalnum() or char.isspace() for char in name):
            raise forms.ValidationError("Category name can only contain letters, numbers, and spaces")
        
        return name.title()

    def clean_description(self):
        description = self.cleaned_data.get('description', '').strip()
        if not description:
            raise forms.ValidationError("Description is required")
        if len(description) < 10:
            raise forms.ValidationError("Description must be at least 10 characters long")
        if len(description) > 500:
            raise forms.ValidationError("Description cannot exceed 500 characters")
        return description

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('category_name')
        description = cleaned_data.get('description')

        if name and description and name.lower() in description.lower():
            self.add_error('description', 
                "Description should not contain the category name")

        return cleaned_data 