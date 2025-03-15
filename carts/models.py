from django.db import models
from store.models import Product


# Create your models here.
class Cart(models.Model):
    cart_id = models.CharField(max_length=250, blank=True)
    date_added = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.cart_id
    
class CartItem(models.Model):
    MAX_QUANTITY = 5
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True)
    quantity = models.IntegerField()
    is_active = models.BooleanField(default=True)

    @property
    def sub_total(self):
        return self.product.price * self.quantity
    
    def get_max_allowed_quantity(self):
        return min(self.MAX_QUANTITY, self.product.stock)

    def __str__(self):
        return f"{self.product.product_name} ({self.quantity})"