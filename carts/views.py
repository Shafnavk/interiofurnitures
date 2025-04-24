# First, update your views.py to handle AJAX requests for the update_quantity view

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from store.models import Product
from .models import Cart, CartItem


# Create your views here.

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def add_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if not product.is_available:
        messages.error(request, 'This product is currently unavailable.')
        return redirect('store')
    if product.stock <= 0:
        messages.error(request, 'This product is out of stock.')
        return redirect('store')
    
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request))
    except Cart.DoesNotExist:
        cart = Cart.objects.create(cart_id=_cart_id(request))
    cart.save()

    quantity = int(request.POST.get('quantity', 1))
 
    if quantity <= 0:
        messages.error(request, 'Invalid quantity.')
        return redirect('store')

    try:
        cart_item = CartItem.objects.get(product=product, cart=cart)
        max_allowed = cart_item.get_max_allowed_quantity()
        
        if cart_item.quantity + quantity > max_allowed:
            messages.warning(request, f'Maximum {max_allowed} items allowed per product.')
            return redirect('cart')
            
        cart_item.quantity += quantity
        cart_item.save()
        messages.success(request, f'{product.product_name} added to cart.')

    except CartItem.DoesNotExist:
        temp_cart_item = CartItem(product=product, cart=cart)
        max_allowed = temp_cart_item.get_max_allowed_quantity()
        
        if quantity > max_allowed:
            messages.warning(request, f'Maximum {max_allowed} items allowed per product.')
            quantity = max_allowed
            
        cart_item = CartItem.objects.create(
            product=product,
            quantity=quantity,
            cart=cart,
        )
        cart_item.save()
        messages.success(request, f'{product.product_name} added to cart.')

    return redirect('cart')

def remove_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart_id = _cart_id(request)
    cart = Cart.objects.get(cart_id=cart_id)
    cart_item = CartItem.objects.get(product=product, cart=cart)
    
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart_item.delete()
        messages.info(request, f'{product.product_name} removed from cart.')
    
    return redirect('cart')

def remove_cart_item(request, cart_item_id):
   
    cart_item = get_object_or_404(CartItem, id=cart_item_id)
    product_name = cart_item.product.product_name
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_item.delete()
        
       
        cart = cart_item.cart
        cart_items = CartItem.objects.filter(cart=cart)
        total = sum(item.product.price * item.quantity for item in cart_items)
        tax = (2 * total) / 100 
        grand_total = total + tax
        
        return JsonResponse({
            'success': True,
            'message': f'{product_name} removed from cart',
            'total': total,
            'tax': tax,
            'grand_total': grand_total
        })
  
    cart_item.delete()
    messages.success(request, f'{product_name} removed from cart.')
    return redirect('cart')

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

# Update the update_quantity function to handle AJAX requests
def update_quantity(request, cart_item_id, action):
    if request.method == 'POST':
        try:
            cart_item = CartItem.objects.get(id=cart_item_id)
            product = cart_item.product
            max_allowed = cart_item.get_max_allowed_quantity()
            
            if action == 'increase':
                if cart_item.quantity >= max_allowed:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': f'Maximum {max_allowed} items allowed per product.'
                        })
                    messages.warning(request, f'Maximum {max_allowed} items allowed per product.')
                    return redirect('cart')
                
                cart_item.quantity += 1
            
            elif action == 'decrease':
                if cart_item.quantity > 1:
                    cart_item.quantity -= 1
                else:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': 'Quantity cannot be less than 1.'
                        })
                    messages.warning(request, 'Quantity cannot be less than 1.')
                    return redirect('cart')
            
            elif action == 'set':
                try:
                    new_quantity = int(request.POST.get('quantity', 1))
                    if new_quantity < 1:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': 'Quantity cannot be less than 1.'
                            })
                        messages.warning(request, 'Quantity cannot be less than 1.')
                        return redirect('cart')
                    if new_quantity > max_allowed:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': f'Maximum {max_allowed} items allowed per product.'
                            })
                        messages.warning(request, f'Maximum {max_allowed} items allowed per product.')
                        new_quantity = max_allowed
                    cart_item.quantity = new_quantity
                except ValueError:
                    return redirect('cart')
            
            cart_item.save()
            
            # If this is an AJAX request, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Recalculate cart totals
                cart = cart_item.cart
                cart_items = CartItem.objects.filter(cart=cart)
                total = 0
                item_count = 0
                
                for item in cart_items:
                    total += (item.product.get_discounted_price * item.quantity)
                    item_count += item.quantity
                
                tax = (2 * total) / 100
                grand_total = total + tax
                
                # Calculate this item's total
                item_total = cart_item.product.get_discounted_price * cart_item.quantity
                
                return JsonResponse({
                    'success': True,
                    'quantity': cart_item.quantity,
                    'item_total': item_total,
                    'total': total,
                    'tax': tax,
                    'grand_total': grand_total,
                    'cart_count': item_count,
                    'message': 'Quantity updated successfully'
                })
            
        except CartItem.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Cart item not found.'
                })
            messages.error(request, 'Cart item not found.')
            
    return redirect('cart')


