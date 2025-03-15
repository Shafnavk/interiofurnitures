from decimal import Decimal
from django import forms
from store.models import Product, ProductImage
from django.core.validators import MinValueValidator, MaxValueValidator
from category.models import Category
from django.utils.text import slugify

class ProductForm(forms.ModelForm):
    specifications = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter product specifications (dimensions, materials, etc.)'
        }),
        required=False
    )
    slug = forms.SlugField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter URL slug'
        }),
        required=False,
    )
    class Meta:
        model = Product
        fields = ['product_name', 'description', 'price', 'stock', 'category', 'is_available']
        widgets = {
            'product_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'minlength': '3',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product description',
                'rows': 4,
                'required': True
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter price',
                'min': '500',
                'step': '1',
                'required': True
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter stock quantity',
                'min': '0',
                'required': True
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean_product_name(self):
        name = self.cleaned_data.get('product_name', '').strip()
        if not name:
            raise forms.ValidationError("Product name is required")
        if len(name) < 3:
            raise forms.ValidationError("Product name must be at least 3 characters long")
       
        if Product.objects.filter(product_name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A product with this name already exists")
        
        return name.title()

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None:
            raise forms.ValidationError("Price is required")
        if price <= Decimal('0'):
            raise forms.ValidationError("Price must be greater than zero")
        if price >= Decimal('10000000'):
            raise forms.ValidationError("Price cannot exceed 10,000,000")
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is None:
            raise forms.ValidationError("Stock quantity is required")
        if stock < 0:
            raise forms.ValidationError("Stock cannot be negative")
        if stock > 10000:
            raise forms.ValidationError("Stock cannot exceed 10,000 units")
        return stock

    def clean_description(self):
        description = self.cleaned_data.get('description', '').strip()
        if not description:
            raise forms.ValidationError("Description is required")
        if len(description) < 10:
            raise forms.ValidationError("Description must be at least 10 characters long")
        if len(description) > 1000:
            raise forms.ValidationError("Description cannot exceed 1000 characters")
        return description 

class ProductImageForm(forms.ModelForm):
    images = forms.FileField(widget = forms.TextInput(attrs={
            "name": "images",
            "type": "File",
            "class": "form-control",
            "multiple": "True",
        }), label = "")
    class Meta:
        model = ProductImage
        fields = ['images']

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category_name', 'slug', 'description', 'is_active']
        widgets = {
            'category_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name',
                'minlength': '2',
                'required': True
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter slug'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category description (minimum 10 characters)',
                'rows': 3,
                'required': True
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        error_messages = {
            'category_name': {
                'unique': 'A category with this name already exists.',
                'required': 'Please enter a category name.',
            },
            'slug': {
                'unique': 'This slug is already in use. Please choose a different one.',
            },
        }

    def clean_category_name(self):
        name = self.cleaned_data.get('category_name', '').strip()
        if not name:
            raise forms.ValidationError("Category name is required")
        if len(name) < 2:
            raise forms.ValidationError("Category name must be at least 2 characters long")
        
        existing = Category.objects.filter(category_name__iexact=name)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise forms.ValidationError(
                f"A category with the name '{name}' already exists. Please choose a different name."
            )
       
        if not all(char.isalnum() or char.isspace() for char in name):
            raise forms.ValidationError("Category name can only contain letters, numbers, and spaces")
        
        return name.title()

    def clean_description(self):
        description = self.cleaned_data.get('description', '').strip()
        if not description:
            raise forms.ValidationError("Description is required")
        if len(description) < 10:
            raise forms.ValidationError("Description must be at least 10 characters long")
        if len(description) > 200:  # Match model's max_length
            raise forms.ValidationError("Description cannot exceed 200 characters")
        return description

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        category_name = self.cleaned_data.get('category_name', '')
        
        if not slug and category_name:
            slug = slugify(category_name)
        elif not slug:
            raise forms.ValidationError("Please provide either a slug or a category name")
       
        existing = Category.objects.filter(slug=slug)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise forms.ValidationError(
                f"A category with the slug '{slug}' already exists. Please choose a different slug."
            )
        
        return slug

    