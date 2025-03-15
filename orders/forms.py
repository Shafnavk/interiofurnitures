from django import forms
from .models import Order
import re
from .locations import COUNTRIES, STATES_BY_COUNTRY

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