from django.conf import settings
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils.text import slugify
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from category.models import Category


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
    
    @property
    def discounted_price(self):
        return self.get_discount
    @property
    def get_discount(self):
        
        from django.utils import timezone
        now = timezone.now()
        
        # Check for product specific offer
        product_offer = ProductOffer.objects.filter(
            product=self,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).order_by('-discount_percentage').first()
        
        # Check for category offer
        category_offer = CategoryOffer.objects.filter(
            category=self.category,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).order_by('-discount_percentage').first()
        
        # Determine which offer gives the better discount
        if product_offer and category_offer:
            if product_offer.discount_percentage >= category_offer.discount_percentage:
                return (product_offer.discount_percentage, product_offer)
            else:
                return (category_offer.discount_percentage, category_offer)
        elif product_offer:
            return (product_offer.discount_percentage, product_offer)
        elif category_offer:
            return (category_offer.discount_percentage, category_offer)
        else:
            return (0, None)

    @property
    def discount_percentage(self):
        
        discount, _ = self.get_discount
        return discount

    @property
    def offer(self):
        
        _, offer = self.get_discount
        return offer

    @property
    def get_discounted_price(self):
       
        discount = self.discount_percentage
        if discount > 0:
            discounted_price = self.price - (self.price * discount / 100)
            return round(discounted_price, 2)
        return self.price
    
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

class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')  
        
    def __str__(self):
        return f"{self.user.username}'s wishlist item: {self.product.product_name}"
    

class BaseOffer(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    discount_percentage = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and 
            self.start_date <= now and 
            self.end_date >= now
        )

class ProductOffer(BaseOffer):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='offers')

    def __str__(self):
        return f"{self.name} - {self.product.product_name}"

class CategoryOffer(BaseOffer):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='offers')

    def __str__(self):
        return f"{self.name} - {self.category.category_name}"