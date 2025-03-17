from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib import messages, auth
from django.contrib.auth.decorators import user_passes_test
from accounts.models import Account
from store.models import Product, ProductImage
from .forms import ProductForm, ProductImageForm
from category.models import Category
from .forms import CategoryForm
from orders.models import Order, OrderProduct
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import base64
from django.core.files.base import ContentFile
import json
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import base64
import json
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

def superuser_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superadmin:
            return view_func(request, *args, **kwargs)
        else:
            return redirect('login')  
    return _wrapped_view

@login_required(login_url="login")
@never_cache
def user_view(request):
    if request.user.is_superadmin:
        return redirect('adminn:adminhome')
    else:
        return render(request, 'home.html')

@never_cache
@superuser_required
def adminhome(request):
    if not request.user.is_superadmin:
        messages.error(request, "You don't have permission to access the admin dashboard.")
        return redirect('dashboard')
    total_users = Account.objects.filter(is_superadmin=False).count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()

    context = {
        "email": request.user.email,
        "first_name": request.user.first_name,
        "total_users": total_users,
        "total_products": total_products,
         "total_orders": total_orders,
    }
    return render(request, 'adminn/adminhome.html', context)  


def users(request):
    accounts = Account.objects.filter(is_superadmin=False)
    context = {'accounts': accounts}
    
    return render(request, 'adminn/users.html', context)

@superuser_required
def blockuser(request, user_id):
    account = Account.objects.get(id=user_id)
    account.is_active = False
    account.save()
    return redirect('adminn:users')  

@superuser_required
def unblockuser(request, user_id):
    account = Account.objects.get(id=user_id)
    account.is_active = True
    account.save()
    return redirect('adminn:users')

@never_cache
@superuser_required
def signout(request):
    auth.logout(request)
    messages.success(request, "you are logged out")
    return redirect('loginn')


@superuser_required
def productlist(request):
    products = Product.objects.filter(is_deleted=False)
    deleted_products = Product.objects.filter(is_deleted=True)
    return render(request, 'adminn/productlist.html', {
        'products': products,
        'deleted_products': deleted_products
    })

@csrf_protect
@superuser_required
@never_cache
def addproduct(request):
    productform = ProductForm()
    imageform = ProductImageForm()
    
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        productform = ProductForm(request.POST, request.FILES)
        
        if productform.is_valid():
            product = productform.save(commit=False)
            product.save()
            
            for file in files:
                
                ProductImage.objects.create(
                    product=product,
                    image=file
                )
            
            return redirect("adminn:productlist")
    
    context = {
        "form": productform, 
        "form_image": imageform
        }
    return render(request, "adminn/addproduct.html", context)

@csrf_protect
@superuser_required
def editproduct(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
        
        if request.method == 'POST':
            form = ProductForm(request.POST, request.FILES, instance=product)
            
            if form.is_valid():
                product = form.save()
                uploaded_images = request.FILES.getlist('images')
                
                for image in uploaded_images:
                    try:
                        
                        ProductImage.objects.create(
                            product=product,
                            image=image
                        )
                        messages.success(request, 'Image uploaded successfully')
                    except Exception as e:
                        messages.error(request, f'Error processing image: {str(e)}')
                
                messages.success(request, 'Product updated successfully')
                return redirect('adminn:productlist')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = ProductForm(instance=product)
        
        context = {
            'form': form,
            'product': product,
            'existing_images': ProductImage.objects.filter(product=product)
        }
        return render(request, 'adminn/editproduct.html', context)
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('adminn:productlist')

@superuser_required   
def delete_product_image(request, image_id):
    if request.method == "POST":
        image = get_object_or_404(ProductImage, id=image_id)
        product_id = image.product.id
        image.delete()
        messages.success(request, "Image deleted successfully")
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})

@superuser_required
def deleteproduct(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.soft_delete()
    messages.success(request, "Product has been unlisted.")
    return redirect('adminn:productlist')

@superuser_required
def restore_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.restore()
    messages.success(request, "Product has been listed successfully.")
    return redirect('adminn:productlist')

@superuser_required
def permanent_delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    messages.success(request, "Product has been permanently deleted.")
    return redirect('adminn:productlist')


def categorylist(request):
    categories = Category.objects.filter(is_deleted=False)
    deleted_categories = Category.objects.filter(is_deleted=True)
    return render(request, 'adminn/categorylist.html', {
        'categories': categories,
        'deleted_categories': deleted_categories
    })

@csrf_protect
@superuser_required
def addcategory(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                category = form.save()
                messages.success(request, f' Category "{category.category_name}" added successfully!')
                return redirect('adminn:categorylist')
            except Exception as e:
                messages.error(request, f'Error saving category: {str(e)}')
    else:
        form = CategoryForm()

    context = {
        'form': form,
        'title': 'Add Category'
    }
    return render(request, 'adminn/addcategory.html', context)

@csrf_protect
@superuser_required
def editcategory(request, category_id):
    category = get_object_or_404(Category, id=category_id, is_deleted=False)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('adminn:categorylist')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'adminn/editcategory.html', {'form': form})

@superuser_required
def deletecategory(request, category_id):
    try:
        category = get_object_or_404(Category, id=category_id)
        category.soft_delete()
        messages.success(request, 'Category has been unlisted.')
    except Exception as e:
        messages.error(request, f'Error deleting category: {str(e)}')
    
    return redirect('adminn:categorylist')

@superuser_required
def restore_category(request, category_id):
    try:
        category = get_object_or_404(Category, id=category_id)
        category.restore()
        messages.success(request, 'Category has been listed successfully.')
    except Exception as e:
        messages.error(request, f'Error restoring category: {str(e)}')
    
    return redirect('adminn:categorylist')

@superuser_required
def permanent_delete_category(request, category_id):
    try:
        category = get_object_or_404(Category, id=category_id)
        category.delete()
        messages.success(request, 'Category has been permanently deleted.')
    except Exception as e:
        messages.error(request, f'Error permanently deleting category: {str(e)}')
    
    return redirect('adminn:categorylist')

@login_required
def admin_orders(request):
    if not request.user.is_superadmin:
        return redirect('home')
        
    orders = Order.objects.all().order_by('-created_at')
    context = {
        'orders': orders,
    }
    return render(request, 'adminn/orders.html', context)

@login_required
def update_order_status(request, order_id):
    if not request.user.is_superadmin:
        return redirect('home')
        
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS):
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id} status updated to {new_status}')
        else:
            messages.error(request, 'Invalid status')
    return redirect('adminn:admin_orders')
