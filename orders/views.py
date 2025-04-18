from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from carts.models import CartItem, Cart
from .models import Coupon, CouponUsage, Order, OrderProduct, Payment, TrackingUpdate, DeliveryCharge
from store.models import Product
from .forms import CouponApplyForm, OrderForm
from accounts.models import Address, Wallet, WalletTransaction
import datetime
from django.db import transaction 
import json
from django.http import JsonResponse
from .locations import STATES_BY_COUNTRY, CITIES_BY_STATE
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from carts.views import _cart_id
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.urls import reverse
from decimal import Decimal

def get_delivery_charge(total, country, state, city):
    
    from decimal import Decimal
    
    total_decimal = Decimal(str(total))
    
    location_charges = DeliveryCharge.objects.filter(
        charge_type='location',
        is_active=True,
        country=country
    ).order_by('amount')
    
    if state:
        state_charges = location_charges.filter(state=state)
        if state_charges.exists():
            location_charges = state_charges
    
    if city:
        city_charges = location_charges.filter(city=city)
        if city_charges.exists():
            location_charges = city_charges
    
    if location_charges.exists():
        charge = location_charges.first()
       
        if charge.free_shipping_threshold > 0 and total_decimal >= charge.free_shipping_threshold:
            return 0
        return float(charge.amount)
    fixed_charges = DeliveryCharge.objects.filter(
        charge_type='fixed',
        is_active=True
    ).order_by('amount').first()
    
    if fixed_charges:
   
        if fixed_charges.free_shipping_threshold > 0 and total_decimal >= fixed_charges.free_shipping_threshold:
            return 0
        return float(fixed_charges.amount)
    
    return 0

def cart(request, total=0, quantity=0, cart_items=None):
    tax = 0
    grand_total = 0
    discount_amount = 0
    
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_items = CartItem.objects.filter(cart=cart)
        
        for cart_item in cart_items:
            if not cart_item.product.is_available:
                cart_item.delete()
                messages.warning(request, f'{cart_item.product.product_name} is no longer available.')
                continue
                
            if cart_item.quantity > cart_item.product.stock:
                cart_item.quantity = cart_item.product.stock
                cart_item.save()
                messages.warning(request, f'Quantity adjusted for {cart_item.product.product_name} due to stock availability.')
                
            item_price = cart_item.product.price
            discounted_price = cart_item.product.get_discounted_price
            
            item_discount = (item_price - discounted_price) * cart_item.quantity
            discount_amount += item_discount
            
            total += (discounted_price * cart_item.quantity)
            quantity += cart_item.quantity
        
        tax = (2 * total) / 100
        grand_total = total + tax
    
    except Cart.DoesNotExist:
        cart_items = []
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'quantity': quantity,
        'tax': tax,
        'discount_amount': discount_amount,
        'grand_total': grand_total,
    }
        
    return render(request, 'store/cart.html', context)

@login_required(login_url='login')
def checkout(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))
    cart_count = cart_items.count()
    
    if cart_count <= 0:
        return redirect('store')
    
    grand_total = 0
    tax = 0
    discount_amount = 0 
    for cart_item in cart_items:
       
        original_price = cart_item.product.price
        discounted_price = cart_item.product.get_discounted_price
        
        item_discount = (original_price - discounted_price) * cart_item.quantity
        discount_amount += item_discount
        
        total += (discounted_price * cart_item.quantity)
        quantity += cart_item.quantity
    
    tax = (2 * total)/100
    
    coupon_id = request.session.get('coupon_id')
    coupon_discount = float(request.session.get('discount', 0))
    
    total_discount = discount_amount + coupon_discount
    
    grand_total = total + tax - coupon_discount

    country = "IN"  
    state = "Kerala"
    city = "calicut"
    
    selected_address_id = request.GET.get('address_id')
    if selected_address_id:
        try:
            selected_address = Address.objects.get(id=selected_address_id, user=current_user)
            request.session['selected_address_id'] = selected_address_id
            country = selected_address.country or country
            state = selected_address.state
            city = selected_address.city
        except Address.DoesNotExist:
            if 'selected_address_id' in request.session:
                del request.session['selected_address_id']
    
    delivery_charge = get_delivery_charge(total, country, state, city)
    
    grand_total_with_delivery = grand_total + delivery_charge
    
    request.session['delivery_charge'] = delivery_charge
    
    cod_available = grand_total_with_delivery <= 1000
    
    coupon = None
    coupon_name = None
    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            coupon_name = coupon.code 
        except Coupon.DoesNotExist:
            if 'coupon_id' in request.session:
                del request.session['coupon_id']
            if 'discount' in request.session:
                del request.session['discount']
            coupon_discount = 0
    
    
    available_coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_to__gte=timezone.now()
    )
   
    eligible_coupons = []
    for avail_coupon in available_coupons:
        if not avail_coupon.minimum_purchase or total >= avail_coupon.minimum_purchase:
            eligible_coupons.append(avail_coupon)
    
    addresses = Address.objects.filter(user=current_user).order_by('-is_default')
    
    coupon_form = CouponApplyForm()
    form = OrderForm()
    
    request.session['order_total'] = float(total)
    
    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
        'delivery_charge': delivery_charge,
        'grand_total_with_delivery': grand_total_with_delivery,
        'form': form,
        'addresses': addresses,
        'coupon_form': coupon_form,
        'coupon': coupon,
        'coupon_name': coupon_name,
        'discount_amount': discount_amount,  
        'coupon_discount': coupon_discount, 
        'total_discount': total_discount,   
        'available_coupons': eligible_coupons,
        'cod_available': cod_available,
        'selected_address_id': selected_address_id,
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

    discount_amount = 0 
    grand_total = 0
    tax = 0
    
    for cart_item in cart_items:
        
        original_price = cart_item.product.price
        discounted_price = cart_item.product.get_discounted_price
        
        item_discount = (original_price - discounted_price) * cart_item.quantity
        discount_amount += item_discount
        
        total += (discounted_price * cart_item.quantity)
        quantity += cart_item.quantity
    
    tax = (2 * total)/100

    coupon_id = request.session.get('coupon_id')
    coupon_discount = float(request.session.get('discount', 0))
    delivery_charge = float(request.session.get('delivery_charge', 0))
    
    total_discount = discount_amount + coupon_discount
    
    grand_total = total + tax - coupon_discount
    grand_total_with_delivery = grand_total + delivery_charge
    
    cod_available = grand_total_with_delivery <= 1000

    if request.method == 'POST':
        address_id = request.POST.get('selected_address')
        save_address = request.POST.get('save_address') == 'on'

        if address_id:
            try:
                address = Address.objects.get(id=address_id, user=current_user)
                
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
                    country= "IN", 
                    pincode=address.pincode,
                    order_total=grand_total_with_delivery,
                    tax=tax,
                    discount_amount=coupon_discount,
                    product_discount=discount_amount,
                    delivery_charge=delivery_charge,
                    ip=request.META.get('REMOTE_ADDR'),
                    is_ordered=False
                )
                
            except Address.DoesNotExist:
                messages.error(request, 'Selected address not found')
                return redirect('checkout')
        else:
           
            form = OrderForm(request.POST)
            if form.is_valid():
                country = form.cleaned_data.get('country', 'IN')
                state = form.cleaned_data.get('state')
                city = form.cleaned_data.get('city')
                
                new_delivery_charge = get_delivery_charge(total, country, state, city)
              
                grand_total_with_delivery = grand_total + new_delivery_charge
                
                order = Order.objects.create(
                    user=current_user,
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    phone=form.cleaned_data['phone'],
                    email=form.cleaned_data['email'],
                    address_line_1=form.cleaned_data['address_line_1'],
                    address_line_2=form.cleaned_data['address_line_2'],
                    country=country,
                    state=state,
                    city=city,
                    pincode=form.cleaned_data['pincode'],
                    order_note=form.cleaned_data.get('order_note', ''),
                    order_total=grand_total_with_delivery,
                    tax=tax,
                    discount_amount=coupon_discount,
                    product_discount=discount_amount,
                    delivery_charge=new_delivery_charge,
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
                        
                        pincode=form.cleaned_data['pincode'],
                        is_default=not Address.objects.filter(user=current_user).exists()
                    )
            else:
                messages.error(request, 'Please correct the errors in the form')
                return redirect('checkout')
                
        if coupon_id:
            try:
                coupon = Coupon.objects.get(id=coupon_id)
                order.coupon = coupon
                order.save()
            except Coupon.DoesNotExist:
                pass
    
        yr = int(datetime.date.today().strftime('%Y'))
        dt = int(datetime.date.today().strftime('%d'))
        mt = int(datetime.date.today().strftime('%m'))
        d = datetime.date(yr,mt,dt)
        current_date = d.strftime("%Y%m%d")
        order_number = current_date + str(order.id)
        order.order_number = order_number
        order.save()

        if coupon_id:
            try:
                coupon = Coupon.objects.get(id=coupon_id)
           
                CouponUsage.objects.create(
                    coupon=coupon,
                    user=current_user,
                    order=order
                )
                
                coupon.times_used += 1
                coupon.save()
                
                if 'coupon_id' in request.session:
                    del request.session['coupon_id']
                if 'discount' in request.session:
                    del request.session['discount']
                    
            except Coupon.DoesNotExist:
                pass

        if 'selected_address_id' in request.session:
            del request.session['selected_address_id']
        
        if 'delivery_charge' in request.session:
            del request.session['delivery_charge']

        context = {
            'order': order,
            'cart_items': cart_items,
            'total': total,
            'tax': tax,
            'grand_total': grand_total,
            'delivery_charge': order.delivery_charge,
            'grand_total_with_delivery': order.order_total,
            'discount_amount': discount_amount,
            'coupon_discount': coupon_discount,
            'total_discount': total_discount,
            'cod_available': cod_available,
        }
        return render(request, 'orders/payments.html', context)

    return redirect('checkout')

@login_required(login_url='login')
def confirm_cod(request, order_number):
    try:
        order = Order.objects.get(order_number=order_number, user=request.user, is_ordered=False)
        
        if order.order_total > 1000:
            messages.error(request, 'Cash On Delivery is not available for orders above $1000.')
            return redirect('checkout')
        
        cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))
        
        total = 0
        quantity = 0
        discount_amount = 0
        
        for cart_item in cart_items:
            original_price = cart_item.product.price
            discounted_price = cart_item.product.get_discounted_price
            
            item_discount = (original_price - discounted_price) * cart_item.quantity
            discount_amount += item_discount
            
            total += (discounted_price * cart_item.quantity)
            quantity += cart_item.quantity
        
        tax = (2 * total)/100
        
        coupon_discount = order.discount_amount or 0
        total_discount = discount_amount + coupon_discount
        
        delivery_charge = order.delivery_charge
        grand_total_with_delivery = order.order_total
        
        context = {
            'order': order,
            'cart_items': cart_items,
            'total': total,
            'tax': tax,
            'delivery_charge': delivery_charge,
            'grand_total_with_delivery': grand_total_with_delivery,
            'discount_amount': discount_amount,
            'coupon_discount': coupon_discount,
            'total_discount': total_discount,
        }
        
        return render(request, 'orders/confirm_cod.html', context)
    
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('checkout')

def payments(request):
    try:
        if request.method == 'POST':
            body = json.loads(request.body)
            order_number = body.get('order_number')
            payment_method = body.get('payment_method')
            
            order = Order.objects.get(
                order_number=order_number,
                user=request.user,
                is_ordered=False
            )
            
            order.payment_method = payment_method
            
            with transaction.atomic():
                if payment_method == 'PayPal':
                    transaction_id = body.get('transID')
                    payment_status = body.get('payment_status', 'Completed')
                    
                    payment = Payment(
                        user=request.user,
                        payment_id=transaction_id,
                        payment_method=payment_method,
                        amount_paid=str(order.order_total),
                        status=payment_status
                    )
                    payment.save()
                    
                    tracking_update = TrackingUpdate(
                        order=order,
                        status='Order Placed',
                        description=f'Order placed successfully with {payment_method} payment.'
                    )
                    tracking_update.save()
                    
                    estimated_delivery = datetime.date.today() + datetime.timedelta(days=7)
                    order.estimated_delivery_date = estimated_delivery
            
                order.is_ordered = True
                order.status = 'New'
                order.save()
                
                cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))
                
                for item in cart_items:
                    orderproduct = OrderProduct()
                    orderproduct.order_id = order.id
                    orderproduct.user_id = request.user.id
                    orderproduct.product_id = item.product_id
                    orderproduct.quantity = item.quantity
                    orderproduct.product_price = item.product.get_discounted_price 
                    orderproduct.original_price = item.product.price 
                    orderproduct.ordered = True
                    orderproduct.save()
                
                    product = Product.objects.get(id=item.product_id)
                    product.stock -= item.quantity
                    product.save()
                
                if order.coupon:
                    coupon_usage = CouponUsage(
                        coupon=order.coupon,
                        user=request.user,
                        order=order
                    )
                    coupon_usage.save()
                
                    order.coupon.times_used += 1
                    order.coupon.save()
                    
                    if 'coupon_id' in request.session:
                        del request.session['coupon_id']
                    if 'discount' in request.session:
                        del request.session['discount']
                
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
                pass
            
            data = {
                'order_number': order.order_number,
                'transaction_id': transaction_id if payment_method == 'PayPal' else '',
            }
            
            return JsonResponse(data)
        
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        print('Payment processing error:', str(e))
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
def wallet_payment(request):
    if request.method == 'POST':
        order_number = request.POST.get('order_number')
        
        try:
            order = Order.objects.get(order_number=order_number, user=request.user, is_ordered=False)
            wallet = Wallet.objects.get(user=request.user)
            
            order_total = Decimal(str(order.order_total))
            
            if wallet.balance < order_total:
                return JsonResponse({'error': 'Insufficient wallet balance'}, status=400)
           
            with transaction.atomic():
                payment = Payment(
                    user=request.user,
                    payment_id=f"WALLET-{order.order_number}",
                    payment_method='Wallet',
                    amount_paid=str(order_total),
                    status='Completed'
                )
                payment.save()
                
                wallet.balance -= order_total
                wallet.save()
                
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=order_total,
                    transaction_type='PAYMENT',
                    description=f'Payment for order #{order.order_number}',
                    order=order
                )
                
                order.payment = payment
                order.is_ordered = True
                order.status = 'New'
                order.payment_method = 'Wallet'
                
                estimated_delivery = datetime.date.today() + datetime.timedelta(days=7)
                order.estimated_delivery_date = estimated_delivery
                order.save()
                
                TrackingUpdate.objects.create(
                    order=order,
                    status='Order Placed',
                    description='Order placed successfully with Wallet payment.'
                )
                
                cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))
                
                for item in cart_items:
                    orderproduct = OrderProduct()
                    orderproduct.order_id = order.id
                    orderproduct.user_id = request.user.id
                    orderproduct.product_id = item.product_id
                    orderproduct.quantity = item.quantity
                    orderproduct.product_price = item.product.get_discounted_price  
                    orderproduct.original_price = item.product.price 
                    orderproduct.ordered = True
                    orderproduct.save()
                    
                    product = Product.objects.get(id=item.product_id)
                    product.stock -= item.quantity
                    product.save()
                
                if order.coupon:
                    coupon_usage = CouponUsage(
                        coupon=order.coupon,
                        user=request.user,
                        order=order
                    )
                    coupon_usage.save()
                    
                    order.coupon.times_used += 1
                    order.coupon.save()
                    
                    if 'coupon_id' in request.session:
                        del request.session['coupon_id']
                    if 'discount' in request.session:
                        del request.session['discount']
                
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
                pass
            
            data = {
                'order_number': order.order_number,
            }
            
            return JsonResponse(data)
            
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)
        except Wallet.DoesNotExist:
            return JsonResponse({'error': 'Wallet not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required(login_url='login')
def cash_on_delivery(request, order_number):
    try:
        order = Order.objects.get(order_number=order_number, user=request.user, is_ordered=False)
        
        if order.order_total > 1000:
            messages.error(request, 'Cash On Delivery is not available for orders above $1000.')
            return redirect('checkout')
        
        with transaction.atomic():
            payment = Payment(
                user=request.user,
                payment_id=f"COD-{order.order_number}",
                payment_method='COD',
                amount_paid=str(order.order_total),
                status='Pending'  
            )
            payment.save()
            
            order.payment_method = 'COD'
            order.is_ordered = True
            order.status = 'New'
            
            estimated_delivery = datetime.date.today() + datetime.timedelta(days=7)
            order.estimated_delivery_date = estimated_delivery
            
            order.save()
            
            tracking_update = TrackingUpdate(
                order=order,
                status='Order Placed',
                description='Order placed successfully with Cash On Delivery.'
            )
            tracking_update.save()
            
            cart_items = CartItem.objects.filter(cart__cart_id=_cart_id(request))
            
            for item in cart_items:
                orderproduct = OrderProduct()
                orderproduct.order_id = order.id
                orderproduct.user_id = request.user.id
                orderproduct.product_id = item.product_id
                orderproduct.quantity = item.quantity
                orderproduct.product_price = item.product.get_discounted_price
                orderproduct.original_price = item.product.price
                orderproduct.ordered = True
                orderproduct.save()
                
                product = Product.objects.get(id=item.product_id)
                product.stock -= item.quantity
                product.save()
            
            if order.coupon:
                coupon_usage = CouponUsage(
                    coupon=order.coupon,
                    user=request.user,
                    order=order
                )
                coupon_usage.save()
                
                order.coupon.times_used += 1
                order.coupon.save()
                
                if 'coupon_id' in request.session:
                    del request.session['coupon_id']
                if 'discount' in request.session:
                    del request.session['discount']

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
            pass
        
        return redirect(reverse('order_complete') + f'?order_number={order.order_number}')  
    
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('checkout')   

def order_complete(request):
    order_number = request.GET.get('order_number')
    payment_method = request.GET.get('payment_method')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = 0
        discount_amount = 0
        
        for item in ordered_products:
            subtotal += item.product_price * item.quantity
            
            item_discount = (item.original_price - item.product_price) * item.quantity
            discount_amount += item_discount

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'payment_method': payment_method or order.payment_method,
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'coupon_discount': order.discount_amount,
            'delivery_charge': order.delivery_charge,
            'total_discount': discount_amount + order.discount_amount,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Order.DoesNotExist):
        return redirect('home')
    

@login_required
def apply_coupon(request):
    if request.method == 'POST':
        form = CouponApplyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            
            try:
                coupon = Coupon.objects.get(code__iexact=code, is_active=True)
                
                total_amount = request.session.get('order_total', 0)
                
                if not coupon.is_valid(total_amount):
                    messages.error(request, "This coupon cannot be applied to your order.")
                    return redirect('checkout')
                
                discount = coupon.get_discount_amount(total_amount)
               
                request.session['coupon_id'] = coupon.id
                request.session['discount'] = float(discount)
                
                messages.success(request, f"Coupon '{code}' applied successfully!")
                
            except Coupon.DoesNotExist:
                messages.error(request, "Invalid coupon code.")
                
        return redirect('checkout')
        
@login_required
def remove_coupon(request):
    if 'coupon_id' in request.session:
        del request.session['coupon_id']
    
    if 'discount' in request.session:
        del request.session['discount']
    
    return redirect('checkout')