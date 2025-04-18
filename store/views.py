from itertools import product
from django.shortcuts import render, get_object_or_404

from carts.models import CartItem

from django.db.models import Q
from category.models import Category
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from carts.views import _cart_id
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import  Product, Wishlist

# Create your views here.
def store(request, category_slug=None):
    categories = None
    products = None
  
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    stock_status = request.GET.get('stock_status')
    sort_by = request.GET.get('sort_by')
    
    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True, is_deleted=False)
    else:
        products = Product.objects.all().filter(is_available=True, is_deleted=False)

    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
 
    if stock_status:
        if stock_status == 'in_stock':
            products = products.filter(stock__gt=5)
        elif stock_status == 'low_stock':
            products = products.filter(stock__gt=0, stock__lte=5)
        elif stock_status == 'out_of_stock':
            products = products.filter(stock=0)

    if sort_by:
        if sort_by == 'price_asc':
            products = products.order_by('price')
        elif sort_by == 'price_desc':
            products = products.order_by('-price')
        elif sort_by == 'newest':
            products = products.order_by('-created_date')
        
    else:

        products = products.order_by('-created_date')
    
    product_count = products.count()
    
    paginator = Paginator(products, 6)  
    page = request.GET.get('page', 1)  
    
    try:
        paged_products = paginator.page(page)
    except PageNotAnInteger:
        paged_products = paginator.page(1)
    except EmptyPage:
        paged_products = paginator.page(paginator.num_pages)

    wishlist_product_ids = []
    if request.user.is_authenticated:
        wishlist_product_ids = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)
    
    
    context = {
        'products': paged_products,
        'product_count': product_count,
        'selected_min': min_price,
        'selected_max': max_price,
        'wishlist_product_ids': wishlist_product_ids,
    }
    return render(request, 'store/store.html', context)

def product_detail(request, category_slug, product_slug):
    try:
        single_product = get_object_or_404(Product, category__slug=category_slug, slug=product_slug, is_deleted=False)
        
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()

        in_wishlist = False
        wishlist_product_ids = []
        
        if request.user.is_authenticated:
            in_wishlist = Wishlist.objects.filter(user=request.user, product=single_product).exists()
            wishlist_product_ids = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)
        
        related_products = Product.objects.filter(category=single_product.category, is_deleted=False).exclude(id=single_product.id)[:2]
        
        discount_percentage = single_product.discount_percentage
        offer = single_product.offer

    except Exception as e:
        raise e
    
    context = {
        'single_product': single_product,
        'related_products': related_products,
        'in_cart': in_cart,
        'in_wishlist': in_wishlist,
        'wishlist_product_ids': wishlist_product_ids,
        'discount_percentage': discount_percentage,
        'offer': offer,
    }
    return render(request, 'store/product_detail.html', context)

def search(request):
    keyword = request.GET.get('keyword', None)
    category_slug = request.GET.get('category', None)
    products = Product.objects.filter(is_deleted=False)

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)  
        products = products.filter(category=category)  

    if keyword:
        products = products.filter(Q(description__icontains=keyword) | Q(product_name__icontains=keyword))

    product_count = products.count()

    context = {
        'products': products,
        'product_count': product_count,
        'category': category if category_slug else None,
    }
    return render(request, 'store/store.html', context)

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    
    if created:
        messages.success(request, 'Product added to wishlist')
    else:
        messages.info(request, 'Product is already in your wishlist')
    return redirect(request.META.get('HTTP_REFERER', 'store'))

@login_required
def remove_from_wishlist(request, product_id):
    Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    messages.success(request, 'Product removed from wishlist')
    return redirect(request.META.get('HTTP_REFERER', 'store'))

@login_required
def wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    context = {
        'wishlist_items': wishlist_items,
    }
    return render(request, 'store/wishlist.html', context)
