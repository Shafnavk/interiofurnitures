from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from carts.models import CartItem
from .models import Order, OrderProduct
from store.models import Product
from .forms import OrderForm
from accounts.models import Address
import datetime
import json
from django.http import JsonResponse
from .locations import STATES_BY_COUNTRY, CITIES_BY_STATE
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from carts.views import _cart_id
from django.contrib import messages

@login_required(login_url='login')
def checkout(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))
    cart_count = cart_items.count()
    
    if cart_count <= 0:
        return redirect('store')

    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2 * total)/100
    grand_total = total + tax

    addresses = Address.objects.filter(user=current_user).order_by('-is_default')
    
    form = OrderForm()

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
        'form': form,
        'addresses': addresses,
    }
    return render(request, 'orders/checkout.html', context)

def get_states(request):
    country_code = request.GET.get('country')
    states = STATES_BY_COUNTRY.get(country_code, [])
    return JsonResponse({'states': states})

def get_cities(request):
    state_code = request.GET.get('state')
    cities = CITIES_BY_STATE.get(state_code, [])
    return JsonResponse({'cities': cities})
 

@login_required(login_url='login')
def place_order(request, total=0, quantity=0):
    current_user = request.user

    cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')

    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2 * total)/100
    grand_total = total + tax

    if request.method == 'POST':
        address_id = request.POST.get('selected_address')
        save_address = request.POST.get('save_address') == 'on'

        if address_id:
            try:
                address = Address.objects.get(id=address_id, user=current_user)
                print(f"Found address: {address.full_name}, {address.address_line_1}")
               
                name_parts = address.full_name.split()
                first_name = name_parts[0] if name_parts else ""
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ""
              
                order = Order.objects.create(
                    user=current_user,
                    first_name=first_name,
                    last_name=last_name,
                    phone=address.phone,
                    email=current_user.email,
                    address_line_1=address.address_line_1,
                    address_line_2=address.address_line_2 or "",  
                    city=address.city,
                    state=address.state,
                    country="IN", 
                    pincode=address.pincode,
                    order_total=grand_total,
                    tax=tax,
                    ip=request.META.get('REMOTE_ADDR'),
                    is_ordered=False
                )
                print(f"Created order with ID: {order.id}")
                
            except Address.DoesNotExist:
                messages.error(request, 'Selected address not found')
                return redirect('checkout')
        else:
           
            form = OrderForm(request.POST)
            if form.is_valid():
                order = Order.objects.create(
                    user=current_user,
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    phone=form.cleaned_data['phone'],
                    email=form.cleaned_data['email'],
                    address_line_1=form.cleaned_data['address_line_1'],
                    address_line_2=form.cleaned_data['address_line_2'],
                    country=form.cleaned_data['country'],
                    state=form.cleaned_data['state'],
                    city=form.cleaned_data['city'],
                    pincode=form.cleaned_data['pincode'],
                    order_note=form.cleaned_data.get('order_note', ''),
                    order_total=grand_total,
                    tax=tax,
                    ip=request.META.get('REMOTE_ADDR'),
                    is_ordered=False  
                )

                if save_address:
                    Address.objects.create(
                        user=current_user,
                        full_name=f"{form.cleaned_data['first_name']} {form.cleaned_data['last_name']}",
                        phone=form.cleaned_data['phone'],
                        address_line_1=form.cleaned_data['address_line_1'],
                        address_line_2=form.cleaned_data['address_line_2'],
                        city=form.cleaned_data['city'],
                        state=form.cleaned_data['state'],
                        pincode=form.cleaned_data['pincode'],
                        is_default=not Address.objects.filter(user=current_user).exists()
                    )
            else:
                messages.error(request, 'Please correct the errors in the form')
                return redirect('checkout')

        yr = int(datetime.date.today().strftime('%Y'))
        dt = int(datetime.date.today().strftime('%d'))
        mt = int(datetime.date.today().strftime('%m'))
        d = datetime.date(yr,mt,dt)
        current_date = d.strftime("%Y%m%d")
        order_number = current_date + str(order.id)
        order.order_number = order_number
        order.save()

        context = {
            'order': order,
            'cart_items': cart_items,
            'total': total,
            'tax': tax,
            'grand_total': grand_total,
        }
        return render(request, 'orders/payments.html', context)

    return redirect('checkout')

def payments(request):
    try:
        if request.method == 'POST':
            body = json.loads(request.body)
            order_number = body.get('order_number')
  
            order = Order.objects.get(
                order_number=order_number,
                user=request.user,
                is_ordered=False
            )

            order.payment_method = body['payment_method']
            order.is_ordered = True
            order.save()

            cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))

            for item in cart_items:
                orderproduct = OrderProduct()
                orderproduct.order_id = order.id
                orderproduct.user_id = request.user.id
                orderproduct.product_id = item.product_id
                orderproduct.quantity = item.quantity
                orderproduct.product_price = item.product.price
                orderproduct.ordered = True
                orderproduct.save()

                product = Product.objects.get(id=item.product_id)
                product.stock -= item.quantity
                product.save()

            CartItem.objects.filter(cart__cart_id=_cart_id(request)).delete()

            try:
                mail_subject = 'Thank you for your order!'
                message = render_to_string('orders/order_received_email.html', {
                    'user': request.user,
                    'order': order,
                })
                to_email = request.user.email
                send_email = EmailMessage(mail_subject, message, to=[to_email])
                send_email.send()
            except Exception as e:
                print('Email sending failed:', str(e))

            data = {
                'order_number': order.order_number,
                'payment_method': order.payment_method,
            }
            return JsonResponse(data)
        
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

def order_complete(request):
    order_number = request.GET.get('order_number')
    payment_method = request.GET.get('payment_method')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = 0
        for i in ordered_products:
            subtotal += i.product_price * i.quantity

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'payment_method': payment_method,
            'subtotal': subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Order.DoesNotExist):
        return redirect('home')

