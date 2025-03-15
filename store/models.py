from django.db import models
from django.urls import reverse

from django.utils.text import slugify
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone

class Product(models.Model):
    product_name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(max_length=500, blank=True)
    specifications = models.TextField(max_length=500, blank=True)
    price = models.IntegerField()
    stock = models.IntegerField()
    is_available = models.BooleanField(default=True)
    category = models.ForeignKey('category.Category', on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.product_name)
            # Handle duplicates with a counter
            original_slug = self.slug
            count = 1
            while Product.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{count}"
                count += 1
        super().save(*args, **kwargs)

    def get_url(self):
        try:
            if not self.slug:
                self.slug = slugify(self.product_name)
                self.save()
            if not self.category.slug:
                self.category.slug = slugify(self.category.category_name)
                self.category.save()
            return reverse('product_detail', args=[self.category.slug, self.slug])
        except:
            return '#'

    def __str__(self):
        return self.product_name

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_available = False
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.is_available = True
        self.save()

    @property
    def main_image(self):
        return self.images.first()
    
    class Meta:
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['is_deleted']),
            models.Index(fields=['is_available']),
        ]

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='products', blank=True, null=True)
    
    class Meta:
        ordering = ['id'] 
    
    def __str__(self):
        return f"Image for {self.product.product_name}"
    
    @property
    def image_url(self):
        
        if self.image:
            return self.image.url
        return None
    
