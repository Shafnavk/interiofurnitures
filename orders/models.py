from django.db import models
from accounts.models import Account
from store.models import Product    
from django.contrib.auth.models import User  # Use your existing user model
from django.core.validators import MinValueValidator, MaxValueValidator

from django.conf import settings 
from decimal import Decimal
from django.utils import timezone

class Payment(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    amount_paid = models.CharField(max_length=100)
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.payment_id

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=[
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    max_usage = models.IntegerField(default=1)
    times_used = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

    def is_valid(self, total_amount):
        
        now = timezone.now()
        total = Decimal(str(total_amount))
        
        if not self.is_active:
            return False
        if not (self.valid_from <= now <= self.valid_to):
            return False
        
        if self.times_used >= self.max_usage:
            return False
        
        if total < self.minimum_purchase:
            return False
        
        return True

    def get_discount_amount(self, total_amount):
        total = Decimal(str(total_amount))  
        
        if self.discount_type == 'percentage':
            discount = (self.discount_value / Decimal('100')) * total
            return discount
        else: 
            discount = min(self.discount_value, total) 
            return discount

class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['coupon', 'user'] 

class TrackingUpdate(models.Model):
    STATUS_CHOICES = (
        ('Order Placed', 'Order Placed'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('In Transit', 'In Transit'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
    )
    
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='tracking_updates')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    location = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.status}"


class Order(models.Model):
    
    STATUS = (
        ('New', 'New'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Refunded', 'Refunded'),
    )

    PAYMENT_METHOD = (
        ('COD', 'COD'),
        ('Razorpay', 'Razorpay'),
        ('Wallet', 'Wallet'),
        ('PayPal', 'Paypal'),
    )

    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    order_number = models.CharField(max_length=20)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    email = models.EmailField(max_length=50)
    address_line_1 = models.CharField(max_length=100)
    address_line_2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    pincode = models.CharField(max_length=10)
    order_note = models.CharField(max_length=100, blank=True)
    order_total = models.FloatField()
    tax = models.FloatField()
    status = models.CharField(max_length=10, choices=STATUS, default='New')
    ip = models.CharField(blank=True, max_length=20)
    is_ordered = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='COD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    discount_amount = models.FloatField(default=0)  
    product_discount = models.FloatField(default=0)
    delivery_charge = models.FloatField(default=0) 
    estimated_delivery_date = models.DateField(null=True, blank=True)
    tracking_number = models.CharField(max_length=50, blank=True, null=True)
    carrier = models.CharField(max_length=50, blank=True, null=True)

    refund_status = models.CharField(max_length=20, choices=(
        ('Not Requested', 'Not Requested'),
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
    ), default='Not Requested')
    
    refund_reason = models.TextField(blank=True, null=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def full_address(self):
        return f'{self.address_line_1} {self.address_line_2}'

    def __str__(self):
        return self.order_number
    def get_total_with_delivery(self):
        return self.order_total + self.delivery_charge

class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    product_price = models.FloatField()
    original_price = models.FloatField(default=0)
    ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product.product_name 



class DeliveryCharge(models.Model):
    CHARGE_TYPE_CHOICES = (
        ('fixed', 'Fixed Charge'),
        ('location', 'Location Based')
    )
    
    name = models.CharField(max_length=100)
    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES, default='fixed')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    
    country = models.CharField(max_length=50, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                                                help_text="Order amount above which delivery is free")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
class ReturnItem(models.Model):
    order_product = models.ForeignKey(OrderProduct, on_delete=models.CASCADE)
    return_quantity = models.IntegerField(default=1)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=(
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
    ), default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Return for {self.order_product.product.product_name} from order {self.order_product.order.order_number}"