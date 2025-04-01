from decimal import Decimal
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib import messages, auth
from django.contrib.auth.decorators import user_passes_test
from accounts.models import Account, Wallet, WalletTransaction
from store.forms import CategoryOfferForm, ProductOfferForm
from orders.forms import CouponForm
from .utils import generate_invoice_pdf, send_invoice_email
from .utils import generate_invoice_pdf, send_invoice_email
from django.core.paginator import Paginator
from store.models import CategoryOffer, Product, ProductImage, ProductOffer
from .forms import ProductForm, ProductImageForm
from category.models import Category
from .forms import CategoryForm
from orders.models import Coupon, CouponUsage, Order, OrderProduct
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import base64
from django.core.files.base import ContentFile
import json
from django.utils import timezone
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import base64
import json
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.db.models import Sum, Count, F
from django.http import HttpResponse
from django.db.models import Q
import csv
from django.db import transaction
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from orders.models import Order, OrderProduct, Coupon, CouponUsage,  TrackingUpdate
import xlsxwriter
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.utils import timezone


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
    # Get search query from GET parameters
    search_query = request.GET.get('search', '').strip()

    # Base querysets
    products = Product.objects.filter(is_deleted=False)
    deleted_products = Product.objects.filter(is_deleted=True)

    # Apply search filter if query exists
    if search_query:
        products = products.filter(
            Q(product_name__icontains=search_query) | 
            Q(description__icontains=search_query) | 
            Q(category__category_name__icontains=search_query)
        )
        
        deleted_products = deleted_products.filter(
            Q(product_name__icontains=search_query) | 
            Q(description__icontains=search_query) | 
            Q(category__category_name__icontains=search_query)
        )

    return render(request, 'adminn/productlist.html', {
        'products': products,
        'deleted_products': deleted_products,
        'search_query': search_query  # Pass search query back to template
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
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})

@superuser_required
def deleteproduct(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.soft_delete()
    return redirect('adminn:productlist')

@superuser_required
def restore_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.restore()
    return redirect('adminn:productlist')

@superuser_required
def permanent_delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
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
            return redirect('adminn:categorylist')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'adminn/editcategory.html', {'form': form})

@superuser_required
def deletecategory(request, category_id):
    try:
        category = get_object_or_404(Category, id=category_id)
        category.soft_delete()
    except Exception as e:
        messages.error(request, f'Error deleting category: {str(e)}')
    
    return redirect('adminn:categorylist')

@superuser_required
def restore_category(request, category_id):
    try:
        category = get_object_or_404(Category, id=category_id)
        category.restore()
    except Exception as e:
        messages.error(request, f'Error restoring category: {str(e)}')
    
    return redirect('adminn:categorylist')

@superuser_required
def permanent_delete_category(request, category_id):
    try:
        category = get_object_or_404(Category, id=category_id)
        category.delete()
    except Exception as e:
        messages.error(request, f'Error permanently deleting category: {str(e)}')
    
    return redirect('adminn:categorylist')

@user_passes_test(lambda u: u.is_superadmin)
def admin_coupon_list(request):
    """Display all coupons with filtering options in admin panel"""
    query = request.GET.get('query', '')
    status = request.GET.get('status', '')
    
    coupons = Coupon.objects.all().order_by('-created_at')
    
    if query:
        coupons = coupons.filter(Q(code__icontains=query))
    
    if status:
        if status == 'active':
            coupons = coupons.filter(is_active=True, valid_to__gt=timezone.now())
        elif status == 'expired':
            coupons = coupons.filter(valid_to__lt=timezone.now())
        elif status == 'inactive':
            coupons = coupons.filter(is_active=False)
    
    for coupon in coupons:
        coupon.usage_count = CouponUsage.objects.filter(coupon=coupon).count()
        if timezone.now() > coupon.valid_to:
            coupon.status = "Expired"
        elif not coupon.is_active:
            coupon.status = "Inactive"
        else:
            coupon.status = "Active"

    paginator = Paginator(coupons, 10)
    page = request.GET.get('page')
    paged_coupons = paginator.get_page(page)
    
    context = {
        'coupons': paged_coupons,
        'query': query,
        'status': status,
    }
    
    return render(request, 'adminn/coupon_list.html', context)

@user_passes_test(lambda u: u.is_superadmin)
def admin_add_coupon(request):
    """Add a new coupon in admin panel"""
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save()
            return redirect('adminn:admin_coupon_list')
    else:
        form = CouponForm()
    
    context = {
        'form': form,
        'title': 'Add Coupon',
    }
    
    return render(request, 'adminn/coupon_form.html', context)

@user_passes_test(lambda u: u.is_superadmin)
def admin_edit_coupon(request, coupon_id):
    
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            return redirect('adminn:admin_coupon_list')
    else:
        form = CouponForm(instance=coupon)
    
    context = {
        'form': form,
        'coupon': coupon,
        'title': 'Edit Coupon',
    }
    
    return render(request, 'adminn/coupon_form.html', context)

@user_passes_test(lambda u: u.is_superadmin)
def admin_toggle_coupon(request, coupon_id):
   
    coupon = get_object_or_404(Coupon, id=coupon_id)
    coupon.is_active = not coupon.is_active
    coupon.save()
    
    status = "activated" if coupon.is_active else "deactivated"
   
    return redirect('adminn:admin_coupon_list')

@user_passes_test(lambda u: u.is_superadmin)
def admin_coupon_usage(request, coupon_id):
    """View detailed usage statistics for a specific coupon"""
    coupon = get_object_or_404(Coupon, id=coupon_id)
    usages = CouponUsage.objects.filter(coupon=coupon).select_related('user', 'order')
   
    total_discount = sum(usage.order.discount_amount for usage in usages if usage.order)
    
    context = {
        'coupon': coupon,
        'usages': usages,
        'total_discount': total_discount,
        'usage_count': usages.count(),
    }
    
    return render(request, 'adminn/coupon_usage.html', context)



@login_required
def admin_orders(request):
    if not request.user.is_superadmin:
        return redirect('home')
        
    orders = Order.objects.all().order_by('-created_at')
    context = {
        'orders': orders,
    }
    return render(request, 'adminn/orders.html', context)

def get_valid_next_statuses(current_status):
    """
    Returns a list of valid next statuses based on the current status
    This enforces a logical flow through the order process
    """
    status_flow = {
        'New': ['Processing', 'Cancelled'],
        'Processing': ['Shipped', 'Cancelled'],
        'Shipped': ['Delivered', 'Cancelled'],
        'Delivered': [],  
        'Cancelled': ['New'] 
    }
        
    return status_flow.get(current_status, [])

@login_required
def update_order_status(request, order_id):
    if not request.user.is_superadmin:
        return redirect('home')
        
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        current_status = order.status
        new_status = request.POST.get('status')
      
        valid_next_statuses = get_valid_next_statuses(current_status)
            
        if new_status == current_status:

            pass
        elif new_status in valid_next_statuses:
            
            if new_status == 'Cancelled':
                if order.coupon:
                    pass
  
                order_products = OrderProduct.objects.filter(order=order)
                for order_product in order_products:
                    product = order_product.product
                    product.stock += order_product.quantity
                    product.save()

            elif current_status == 'Cancelled' and new_status == 'New':
               
                can_reactivate = True
                order_products = OrderProduct.objects.filter(order=order)
                        
                for order_product in order_products:
                    if order_product.product.stock < order_product.quantity:
                        can_reactivate = False
                        break
                        
                if can_reactivate:
                    
                    for order_product in order_products:
                        product = order_product.product
                        product.stock -= order_product.quantity
                        product.save()
                                
                    if order.coupon:
                        pass
                else:
                    messages.error(request, 'Cannot reactivate order: Some products are out of stock')
                    return redirect('adminn:admin_orders')
                
            TrackingUpdate.objects.create(
                order=order,
                status=new_status,
                description=f"Order status updated to {new_status}",
                timestamp=timezone.now()
            )

            order.status = new_status
            order.save()
           
        else:
            pass
            
    return redirect('adminn:admin_orders')

@login_required
def manage_order_tracking(request, order_id):
    if not request.user.is_superadmin:
        return redirect('home')
        
    order = get_object_or_404(Order, id=order_id)
    tracking_updates = TrackingUpdate.objects.filter(order=order).order_by('-timestamp')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_tracking_info':
            
            tracking_number = request.POST.get('tracking_number')
            carrier = request.POST.get('carrier')
            estimated_delivery_date = request.POST.get('estimated_delivery_date')
            
            order.tracking_number = tracking_number
            order.carrier = carrier
            
            if estimated_delivery_date:
                try:
                    order.estimated_delivery_date = timezone.datetime.strptime(
                        estimated_delivery_date, '%Y-%m-%d'
                    ).date()
                except ValueError:
                    messages.error(request, 'Invalid date format. Use YYYY-MM-DD.')
                    return redirect('adminn:manage_order_tracking', order_id=order_id)
            
            order.save()
            messages.success(request, 'Tracking information updated successfully.')
            
        elif action == 'add_tracking_update':
            
            status = request.POST.get('status')
            location = request.POST.get('location')
            description = request.POST.get('description')
            
            if status:
                TrackingUpdate.objects.create(
                    order=order,
                    status=status,
                    location=location,
                    description=description,
                    timestamp=timezone.now()
                )
                messages.success(request, 'Tracking update added successfully.')
            else:
                messages.error(request, 'Status is required.')
                
        elif action == 'delete_tracking_update':
            
            update_id = request.POST.get('update_id')
            if update_id:
                try:
                    update = TrackingUpdate.objects.get(id=update_id, order=order)
                    update.delete()
                    messages.success(request, 'Tracking update deleted successfully.')
                except TrackingUpdate.DoesNotExist:
                    messages.error(request, 'Tracking update not found.')
            
        return redirect('adminn:manage_order_tracking', order_id=order_id)
    
    context = {
        'order': order,
        'tracking_updates': tracking_updates,
        'status_choices': TrackingUpdate.STATUS_CHOICES,
    }
    
    return render(request, 'adminn/manage_order_tracking.html', context)

@login_required
def download_invoice(request, order_id):
    if not request.user.is_superadmin:
        return redirect('home')
        
    order = get_object_or_404(Order, id=order_id)
    pdf = generate_invoice_pdf(order)
    
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'
        return response
    
    messages.error(request, 'Error generating invoice')
    return redirect('adminn:admin_orders')

@login_required
def send_invoice(request, order_id):
    if not request.user.is_superadmin:
        return redirect('home')
        
    order = get_object_or_404(Order, id=order_id)
    if send_invoice_email(order):
        messages.success(request, f'Invoice sent to {order.user.email}')
    else:
        messages.error(request, 'Error sending invoice')
    
    return redirect('adminn:admin_orders')



@user_passes_test(lambda u: u.is_superadmin)
def sales_report(request):
  
    date_range = request.GET.get('date_range', 'all')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
  
    end_date = datetime.now().date()
    start_date = end_date
    
    if date_range == 'day':
        start_date = end_date
    elif date_range == 'week':
        start_date = end_date - timedelta(days=7)
    elif date_range == 'month':
        start_date = end_date.replace(day=1)
    elif date_range == 'year':
        start_date = end_date.replace(month=1, day=1)
    elif date_range == 'custom' and start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass 
  
    if date_range == 'all':
        orders = Order.objects.filter(is_ordered=True)
    else:
        orders = Order.objects.filter(
            is_ordered=True,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
   
    total_orders = orders.count()
    order_items = OrderProduct.objects.filter(order__in=orders)
    total_items_sold = order_items.aggregate(total=Sum('quantity'))['total'] or 0
  
    order_totals = orders.aggregate(
        total_sales=Sum('order_total'),
        total_discount=Sum('discount_amount')
    )
    
    total_sales = order_totals['total_sales'] or 0
    total_discount = order_totals['total_discount'] or 0
    net_sales = total_sales - total_discount
  
    coupon_usages = CouponUsage.objects.filter(order__in=orders)
    coupons_used = coupon_usages.values('coupon__code').annotate(
        count=Count('id'),
        total_discount=Sum('order__discount_amount')
    ).order_by('-count')

    daily_sales = orders.values('created_at__date').annotate(
        date=F('created_at__date'),
        orders=Count('id'),
        sales=Sum('order_total'),
        discounts=Sum('discount_amount')
    ).order_by('date')
    
    context = {
        'orders': orders,
        'total_orders': total_orders,
        'total_items_sold': total_items_sold,
        'total_sales': total_sales,
        'total_discount': total_discount,
        'net_sales': net_sales,
        'date_range': date_range,
        'start_date': start_date,
        'end_date': end_date,
        'coupons_used': coupons_used,
        'daily_sales': daily_sales,
    }
 
    export_format = request.GET.get('export')
    if export_format == 'excel':
        return export_excel_report(context)
    elif export_format == 'pdf':
        return export_pdf_report(context)
    
    return render(request, 'adminn/sales_report.html', context)

def export_excel_report(context):
   
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Sales Report')

    title_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'bg_color': '#4A635D',
        'font_color': 'white', 
    })
    
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#ACC7BE', 
        'border': 1,
        'align': 'center',
    })
    
    cell_format = workbook.add_format({
        'border': 1,
    })
    
    report_period = f"{context['start_date']} to {context['end_date']}"
    if context['date_range'] == 'all':
        report_period = "All Time"
    elif context['date_range'] == 'day':
        report_period = f"Day - {context['end_date']}"
    elif context['date_range'] == 'week':
        report_period = f"Week - {context['start_date']} to {context['end_date']}"
    elif context['date_range'] == 'month':
        report_period = f"Month - {context['start_date'].strftime('%B %Y')}"
    elif context['date_range'] == 'year':
        report_period = f"Year - {context['start_date'].year}"
    
    worksheet.merge_range('A1:F1', f'Sales Report - {report_period}', title_format)
    
    worksheet.write('A3', 'Summary', header_format)
    worksheet.merge_range('A3:F3', 'Summary', header_format)
    
    row = 4
    summary_data = [
        ['Total Orders', context['total_orders']],
        ['Total Items Sold', context['total_items_sold']],
        ['Total Sales (₹)', context['total_sales']],
        ['Total Discounts (₹)', context['total_discount']],
        ['Net Sales (₹)', context['net_sales']],
    ]
    
    for item in summary_data:
        worksheet.write(row, 0, item[0], cell_format)
        worksheet.write(row, 1, item[1], cell_format)
        row += 1
   
    row += 2
    worksheet.merge_range(f'A{row}:F{row}', 'Coupon Usage', header_format)
    row += 1
    
    worksheet.write(row, 0, 'Coupon Code', header_format)
    worksheet.write(row, 1, 'Usage Count', header_format)
    worksheet.write(row, 2, 'Total Discount (₹)', header_format)
    row += 1
    
    for coupon in context['coupons_used']:
        worksheet.write(row, 0, coupon['coupon__code'], cell_format)
        worksheet.write(row, 1, coupon['count'], cell_format)
        worksheet.write(row, 2, coupon['total_discount'], cell_format)
        row += 1
  
    row += 2
    worksheet.merge_range(f'A{row}:F{row}', 'Daily Sales Breakdown', header_format)
    row += 1
    
    worksheet.write(row, 0, 'Date', header_format)
    worksheet.write(row, 1, 'Orders', header_format)
    worksheet.write(row, 2, 'Sales (₹)', header_format)
    worksheet.write(row, 3, 'Discounts (₹)', header_format)
    worksheet.write(row, 4, 'Net Sales (₹)', header_format)
    row += 1
    
    for day in context['daily_sales']:
        net = day['sales'] - day['discounts']
        worksheet.write(row, 0, str(day['date']), cell_format)
        worksheet.write(row, 1, day['orders'], cell_format)
        worksheet.write(row, 2, day['sales'], cell_format)
        worksheet.write(row, 3, day['discounts'], cell_format)
        worksheet.write(row, 4, net, cell_format)
        row += 1
 
    row += 2
    worksheet.merge_range(f'A{row}:F{row}', 'Order Details', header_format)
    row += 1
    
    worksheet.write(row, 0, 'Order ID', header_format)
    worksheet.write(row, 1, 'Date', header_format)
    worksheet.write(row, 2, 'Customer', header_format)
    worksheet.write(row, 3, 'Order Total (₹)', header_format)
    worksheet.write(row, 4, 'Discount (₹)', header_format)
    worksheet.write(row, 5, 'Net Total (₹)', header_format)
    row += 1
    
    for order in context['orders']:
        worksheet.write(row, 0, order.order_number, cell_format)
        worksheet.write(row, 1, str(order.created_at.date()), cell_format)
        worksheet.write(row, 2, order.user.email, cell_format)
        worksheet.write(row, 3, order.order_total, cell_format)
        worksheet.write(row, 4, order.discount_amount, cell_format)
        worksheet.write(row, 5, order.order_total - order.discount_amount, cell_format)
        row += 1
    
    workbook.close()
    output.seek(0)
    
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def export_pdf_report(context):
    
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']

    report_period = f"{context['start_date']} to {context['end_date']}"
    if context['date_range'] == 'all':
        report_period = "All Time"
    elif context['date_range'] == 'day':
        report_period = f"Day - {context['end_date']}"
    elif context['date_range'] == 'week':
        report_period = f"Week - {context['start_date']} to {context['end_date']}"
    elif context['date_range'] == 'month':
        report_period = f"Month - {context['start_date'].strftime('%B %Y')}"
    elif context['date_range'] == 'year':
        report_period = f"Year - {context['start_date'].year}"
    
    elements.append(Paragraph(f"Sales Report - {report_period}", title_style))
    elements.append(Paragraph(" ", normal_style))
   
    elements.append(Paragraph("Summary", subtitle_style))
    
    summary_data = [
        ['Metric', 'Value'],
        ['Total Orders', str(context['total_orders'])],
        ['Total Items Sold', str(context['total_items_sold'])],
        ['Total Sales (₹)', str(context['total_sales'])],
        ['Total Discounts (₹)', str(context['total_discount'])],
        ['Net Sales (₹)', str(context['net_sales'])],
    ]
    
    summary_table = Table(summary_data, colWidths=[250, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.black),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (1, 0), 12),
        ('GRID', (0, 0), (1, -1), 1, colors.black),
    ]))
    
    elements.append(summary_table)
    elements.append(Paragraph(" ", normal_style))
 
    if context['coupons_used']:
        elements.append(Paragraph("Coupon Usage", subtitle_style))
        
        coupon_data = [['Coupon Code', 'Usage Count', 'Total Discount (₹)']]
        for coupon in context['coupons_used']:
            coupon_data.append([
                coupon['coupon__code'],
                str(coupon['count']),
                str(coupon['total_discount'])
            ])
        
        coupon_table = Table(coupon_data, colWidths=[150, 100, 150])
        coupon_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (2, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (2, 0), colors.black),
            ('ALIGN', (0, 0), (2, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (2, 0), 12),
            ('GRID', (0, 0), (2, -1), 1, colors.black),
        ]))
        
        elements.append(coupon_table)
        elements.append(Paragraph(" ", normal_style))
 
    if context['daily_sales']:
        elements.append(Paragraph("Daily Sales Breakdown", subtitle_style))
        
        daily_data = [['Date', 'Orders', 'Sales (₹)', 'Discounts (₹)', 'Net Sales (₹)']]
        for day in context['daily_sales']:
            net = day['sales'] - day['discounts']
            daily_data.append([
                str(day['date']),
                str(day['orders']),
                str(day['sales']),
                str(day['discounts']),
                str(net)
            ])
        
        daily_table = Table(daily_data, colWidths=[100, 70, 100, 100, 100])
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (4, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (4, 0), colors.black),
            ('ALIGN', (0, 0), (4, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (4, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (4, 0), 12),
            ('GRID', (0, 0), (4, -1), 1, colors.black),
        ]))
        
        elements.append(daily_table)

    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
  
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def export_csv_report(request, context):
    """Export sales report data to CSV format"""
    response = HttpResponse(content_type='text/csv')
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow(['Sales Report', f"{context['start_date']} to {context['end_date']}"])
    writer.writerow([])
   
    writer.writerow(['Summary'])
    writer.writerow(['Total Orders', context['total_orders']])
    writer.writerow(['Total Items Sold', context['total_items_sold']])
    writer.writerow(['Total Sales (₹)', context['total_sales']])
    writer.writerow(['Total Discounts (₹)', context['total_discount']])
    writer.writerow(['Net Sales (₹)', context['net_sales']])
    writer.writerow([])
   
    writer.writerow(['Coupon Usage'])
    writer.writerow(['Coupon Code', 'Usage Count', 'Total Discount (₹)'])
    for coupon in context['coupons_used']:
        writer.writerow([
            coupon['coupon__code'],
            coupon['count'],
            coupon['total_discount']
        ])
    writer.writerow([])
  
    writer.writerow(['Order Details'])
    writer.writerow(['Order ID', 'Date', 'Customer', 'Order Total (₹)', 'Discount (₹)', 'Net Total (₹)'])
    for order in context['orders']:
        writer.writerow([
            order.order_number,
            order.created_at.date(),
            order.user.email,
            order.order_total,
            order.discount_amount,
            order.order_total - order.discount_amount
        ])
    
    return response


@login_required(login_url='login')
def process_refund(request, order_id):
   
    if not request.user.is_admin and not request.user.is_superadmin:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard')
    
    order = get_object_or_404(Order, id=order_id)
    
    if order.refund_status != 'Pending':
        messages.error(request, f'This order is not pending refund.')
        return redirect('adminn:admin_orders', order_id=order_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            try:
                with transaction.atomic():
                   
                    wallet, created = Wallet.objects.get_or_create(user=order.user)
                    
                    wallet.balance += Decimal(str(order.order_total))
                    wallet.save()
                   
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=order.order_total,
                        transaction_type='REFUND',
                        description=f'Refund for order #{order.order_number}',
                        order=order
                    )
                    
                    # Update order status
                    order.refund_status = 'Completed'
                    order.status = 'Refunded'
                    order.refunded_at = timezone.now()
                    order.save()
                    
                    messages.success(request, f'Refund of ₹{order.order_total} has been processed to customer wallet.')
            except Exception as e:
                messages.error(request, f'Error processing refund: {str(e)}')
        
        elif action == 'reject':
            order.refund_status = 'Rejected'
            order.save()
            messages.success(request, 'Refund request has been rejected.')
        
        return redirect('adminn:admin_orders')
    
    return render(request, 'adminn/process_refund.html', {'order': order})


@superuser_required
def offers_dashboard(request):
    product_offers = ProductOffer.objects.all().order_by('-created_at')
    category_offers = CategoryOffer.objects.all().order_by('-created_at')
    
    now = timezone.now()
    for offer in product_offers:
        if offer.is_active and offer.start_date <= now and offer.end_date >= now:
            offer.status = "Active"
        elif offer.end_date < now:
            offer.status = "Expired"
        elif offer.start_date > now:
            offer.status = "Scheduled"
        else:
            offer.status = "Inactive"
    
    for offer in category_offers:
        if offer.is_active and offer.start_date <= now and offer.end_date >= now:
            offer.status = "Active"
        elif offer.end_date < now:
            offer.status = "Expired"
        elif offer.start_date > now:
            offer.status = "Scheduled"
        else:
            offer.status = "Inactive"
    
    context = {
        'product_offers': product_offers,
        'category_offers': category_offers,
    }
    
    return render(request, 'adminn/offers/offers_dashboard.html', context)

@superuser_required
def add_product_offer(request):
    if request.method == 'POST':
        form = ProductOfferForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product offer created successfully!')
            return redirect('adminn:offers_dashboard')
    else:
        form = ProductOfferForm()
    
    context = {
        'form': form,
        'title': 'Add Product Offer'
    }
    return render(request, 'adminn/offers/offer_form.html', context)

@superuser_required
def edit_product_offer(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id)
    if request.method == 'POST':
        form = ProductOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product offer updated successfully!')
            return redirect('adminn:offers_dashboard')
    else:
        form = ProductOfferForm(instance=offer)
    
    context = {
        'form': form,
        'title': 'Edit Product Offer'
    }
    return render(request, 'adminn/offers/offer_form.html', context)

@superuser_required
def delete_product_offer(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id)
    offer.delete()
    messages.success(request, 'Product offer deleted successfully!')
    return redirect('adminn:offers_dashboard')

@superuser_required
def toggle_product_offer(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id)
    offer.is_active = not offer.is_active
    offer.save()
    status = "activated" if offer.is_active else "deactivated"
    messages.success(request, f'Product offer {status} successfully!')
    return redirect('adminn:offers_dashboard')

@superuser_required
def add_category_offer(request):
    if request.method == 'POST':
        form = CategoryOfferForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category offer created successfully!')
            return redirect('adminn:offers_dashboard')
    else:
        form = CategoryOfferForm()
    
    context = {
        'form': form,
        'title': 'Add Category Offer'
    }
    return render(request, 'adminn/offers/offer_form.html', context)

@superuser_required
def edit_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    if request.method == 'POST':
        form = CategoryOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category offer updated successfully!')
            return redirect('adminn:offers_dashboard')
    else:
        form = CategoryOfferForm(instance=offer)
    
    context = {
        'form': form,
        'title': 'Edit Category Offer'
    }
    return render(request, 'adminn/offers/offer_form.html', context)

@superuser_required
def delete_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    offer.delete()
    messages.success(request, 'Category offer deleted successfully!')
    return redirect('adminn:offers_dashboard')

@superuser_required
def toggle_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    offer.is_active = not offer.is_active
    offer.save()
    status = "activated" if offer.is_active else "deactivated"
    messages.success(request, f'Category offer {status} successfully!')
    return redirect('adminn:offers_dashboard')