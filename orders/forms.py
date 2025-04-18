from django import forms
from .models import Order
import re
from .locations import COUNTRIES, STATES_BY_COUNTRY
from django import forms
from .models import Coupon, DeliveryCharge    
from django.utils import timezone

class OrderForm(forms.ModelForm):
    
    country = forms.ChoiceField(choices=COUNTRIES)
    state = forms.CharField(widget=forms.Select())
    city = forms.CharField(widget=forms.Select())
    
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'phone', 'email', 'address_line_1', 
                 'address_line_2', 'country', 'state', 'city', 'pincode', 'order_note']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
            
        self.fields['state'].widget.attrs['disabled'] = 'disabled'
        self.fields['city'].widget.attrs['disabled'] = 'disabled'
        
    def clean_phone(self):
        phone = self.cleaned_data['phone']
        phone_digits = re.sub(r'\D', '', phone)
        
        if len(phone_digits) < 10 or len(phone_digits) > 15:
            raise forms.ValidationError("Please enter a valid phone number (10-15 digits)")
        return phone
    
    def clean_pincode(self):
        pincode = self.cleaned_data['pincode']
        if not re.match(r'^[a-zA-Z0-9]{4,10}$', pincode):
            raise forms.ValidationError("Please enter a valid postal/zip code")
        return pincode
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise forms.ValidationError("Please enter a valid email address")
        return email


class CouponForm(forms.ModelForm):
    valid_from = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="When this coupon becomes valid"
    )
    valid_to = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="When this coupon expires"
    )
    
    class Meta:
        model = Coupon
        fields = ['code', 'discount_type', 'discount_value', 'minimum_purchase', 
                  'valid_from', 'valid_to', 'max_usage', 'is_active']
        
    def clean_valid_to(self):
        valid_from = self.cleaned_data.get('valid_from')
        valid_to = self.cleaned_data.get('valid_to')
        
        if valid_from and valid_to and valid_to <= valid_from:
            raise forms.ValidationError("End date must be after start date.")
        
        return valid_to
    
    def clean_discount_value(self):
        discount_type = self.cleaned_data.get('discount_type')
        discount_value = self.cleaned_data.get('discount_value')
        
        if discount_type == 'percentage' and discount_value > 100:
            raise forms.ValidationError("Percentage discount cannot exceed 100%.")
        
        if discount_value <= 0:
            raise forms.ValidationError("Discount must be greater than zero.")
            
        return discount_value


class CouponApplyForm(forms.Form):
    """Form for customers to apply a coupon code"""
    code = forms.CharField(label="Coupon Code", max_length=50)



class DeliveryChargeForm(forms.ModelForm):
    class Meta:
        model = DeliveryCharge
        fields = ['name', 'charge_type', 'amount', 'country', 'state', 'city', 
                  'free_shipping_threshold', 'is_active']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['country'].required = False
        self.fields['state'].required = False
        self.fields['city'].required = False
        
        # Custom field labels and help text
        self.fields['name'].widget.attrs.update({'class': 'form-control'})
        self.fields['charge_type'].widget.attrs.update({'class': 'form-control'})
        self.fields['amount'].widget.attrs.update({'class': 'form-control'})
        self.fields['country'].widget.attrs.update({'class': 'form-control'})
        self.fields['state'].widget.attrs.update({'class': 'form-control'})
        self.fields['city'].widget.attrs.update({'class': 'form-control'})
        self.fields['free_shipping_threshold'].widget.attrs.update({'class': 'form-control'})
        self.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        
    def clean(self):
        cleaned_data = super().clean()
        charge_type = cleaned_data.get('charge_type')
        country = cleaned_data.get('country')
        
        if charge_type == 'location' and not country:
            self.add_error('country', 'Country is required for location-based delivery charges')
        
        return cleaned_data
