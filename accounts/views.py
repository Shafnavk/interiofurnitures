
from django.contrib import messages, auth
from django.shortcuts import redirect, render, get_object_or_404
from . forms import RegistrationForm, UserProfileForm
from . models import Account
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.contrib.messages import get_messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.sites.shortcuts import get_current_site 
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage, send_mail
from . models import Account, Address
import re
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
import secrets
import urllib.parse
import requests
import logging
from django.views.decorators.cache import never_cache
logger = logging.getLogger(__name__)
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import random
from .models import OTP
import datetime
from django.http import JsonResponse
from orders.models import Order, OrderProduct
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_otp_email(email, otp):
    subject = 'Your Email Verification OTP'
    message = f'Your OTP for email verification is: {otp}\nThis OTP will expire in 5 minutes.'
    from_email = settings.DEFAULT_FROM_EMAIL
    send_mail(subject, message, from_email, [email])

@csrf_protect
@never_cache
def register(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        email = None  
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    first_name = form.cleaned_data['first_name']
                    last_name = form.cleaned_data['last_name']
                    email = form.cleaned_data['email']
                    password = form.cleaned_data['password']
                    username = email.split('@')[0]
          
                    # Create inactive user
                    user = Account.objects.create_user(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        username=username,
                        password=password
                    )
                    user.is_active = False
                    user.save()

                    # Generate and save OTP
                    otp_code = generate_otp()
                    otp = OTP.objects.create(
                        user=user,
                        otp=otp_code,
                        expires_at=timezone.now() + timedelta(minutes=5)
                    )
                    try:
                        send_otp_email(email, otp_code)
                        messages.success(
                            request,
                            'Registration successful! Please check your email for the verification code.'
                        )
                        request.session['registration_email'] = email
                        return redirect('verify_otp')
                            
                    except Exception as e:
                        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
                        messages.warning(
                            request,
                            'Registration successful but failed to send verification email. '
                            'Please try again or contact support.'
                        )
                        user.delete()
                    
                    return redirect('register')
                    
            except Exception as e:
                logger.error(f"Registration error for {email or 'unknown email'}: {str(e)}")
                messages.error(
                    request,
                    'An error occurred during registration. Please try again.'
                )        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        messages.error(request, error)
    else:
        form = RegistrationForm()

    context = {
        'form': form,
    }
    return render(request, 'accounts/register.html', context)

@csrf_protect
@never_cache
def verify_otp(request):
    if not request.session.get('registration_email'):
        messages.error(request, 'Please register first.')
        return redirect('register')

    if not request.session.get('otp_verification_started'):
        request.session['otp_verification_started'] = timezone.now().isoformat()
        request.session.set_expiry(600) 
    verification_started = datetime.datetime.fromisoformat(request.session.get('otp_verification_started'))
    if (timezone.now() - verification_started.replace(tzinfo=timezone.get_current_timezone())).seconds > 600:

        request.session.pop('registration_email', None)
        request.session.pop('otp_verification_started', None)
        messages.error(request, 'OTP verification session has expired. Please register again.')
        return redirect('register')

    if request.method == 'POST':
        otp_entered = request.POST.get('otp')
        email = request.session.get('registration_email')
        
        try:
            user = Account.objects.get(email=email, is_active=False)
            otp_obj = OTP.objects.filter(user=user).latest('created_at')
            
            if otp_obj.is_valid():
                if otp_obj.otp == otp_entered:
                    user.is_active = True
                    user.save()
                    OTP.objects.filter(user=user).delete()

                    request.session.pop('registration_email', None)
                    request.session.pop('otp_verification_started', None)
                    
                    messages.success(request, 'Email verified successfully! You can now login.')
                    return redirect('login')
                else:
                    messages.error(request, 'Invalid OTP. Please try again.')
            else:
                messages.error(request, 'OTP has expired. Please request a new one.')
                
        except (Account.DoesNotExist, OTP.DoesNotExist):
            messages.error(request, 'Invalid verification attempt.')
            return redirect('register')
            
    return render(request, 'accounts/verify_otp.html')

@csrf_protect
@never_cache
def resend_otp(request):
    if request.method == 'POST':
        email = request.session.get('registration_email')
        if not email:
            return JsonResponse({'success': False, 'message': 'Please register first.'})
       
        last_resend = request.session.get('last_otp_resend')
        if last_resend:
            last_resend = timezone.datetime.fromisoformat(last_resend)
            time_since_last = (timezone.now() - last_resend).total_seconds()
            if time_since_last < 30:
                return JsonResponse({
                    'success': False, 
                    'message': f'Please wait {30 - time_since_last} seconds before requesting a new OTP.'
                })
            
        try:
            user = Account.objects.get(email=email, is_active=False)
       
            OTP.objects.filter(user=user).delete()
     
            otp_code = generate_otp()
            OTP.objects.create(
                user=user,
                otp=otp_code,
                expires_at=timezone.now() + timedelta(minutes=5)
            )
            
            send_otp_email(email, otp_code)
            
            request.session['last_otp_resend'] = timezone.now().isoformat()
            
            return JsonResponse({'success': True})
            
        except Account.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found.'})
        except Exception as e:
            logger.error(f"Failed to resend OTP: {str(e)}")
            return JsonResponse({'success': False, 'message': 'Failed to send OTP.'})
            
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@never_cache
@csrf_protect
def login_with_google(request):
   
    google_client_id = settings.GOOGLE_CLIENT_ID
    redirect_uri = request.build_absolute_uri(reverse('google_callback'))
    scope = "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"
    state = secrets.token_urlsafe(16)
    request.session['oauth_token'] = state
    
    params = {
        'client_id': google_client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
        'include_granted_scopes': 'true'
    }
    
    # Construct and redirect to Google's authorization URL
    url = f'https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}'
    return redirect(url)

@never_cache
@csrf_protect
def google_callback(request):
    """
    Handles the Google OAuth2 callback and user creation/login.
    """
    if request.method == 'GET':
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        session_state = request.session.get('oauth_token')
        
        request.session.pop('oauth_token', None)

        if error or not state or state != session_state:
            messages.error(request, "Authentication failed")
            return redirect('login')
        
        try:
            # Exchange code for access token
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                'code': code,
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'redirect_uri': request.build_absolute_uri(reverse('google_callback')),
                'grant_type': 'authorization_code'
            }
            
            # Get access token
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()  # Raise exception for bad status codes
            token_json = token_response.json()
            access_token = token_json.get('access_token')
            
            # Get user info from Google
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {'Authorization': f'Bearer {access_token}'}
            user_info_response = requests.get(user_info_url, headers=headers)
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            
            # Extract user information
            email = user_info.get('email')
            full_name = user_info.get('name', '')
            first_name = full_name.split(' ')[0] if full_name else ''
            last_name = full_name.split(' ')[-1] if len(full_name.split(' ')) > 1 else ''
            username = email.split('@')[0]
            
            # Create or get user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'username': username,
                    'is_active': True,
                }
            )
     
            if created:
                user.set_unusable_password()
                user.save()
  
            auth.login(request, user)
            messages.success(request, "Login successful with Google")
            return redirect('user_home')
            
        except requests.exceptions.RequestException as e:
            messages.error(request, f"Authentication failed: {str(e)}")
            return redirect('login')
        except Exception as e:
            messages.error(request, "An unexpected error occurred")
            return redirect('login')
    
    return redirect('login')

@never_cache
@csrf_protect
def login(request):
    if request.user.is_authenticated:
        return redirect('adminn:adminhome' if request.user.is_superadmin else 'home')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Please enter a valid email address!')
            return render(request, 'accounts/login.html')  

        if not Account.objects.filter(email=email).exists():
            messages.error(request, 'Email does not exist!')
            return render(request, 'accounts/login.html') 
        
        user = auth.authenticate(email=email, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'Please activate your account first!')
                return render(request, 'accounts/login.html')  
            
            auth.login(request, user)

            request.session['last_activity'] = timezone.now().isoformat()
            request.session['user_id'] = user.id
            request.session['is_superadmin'] = user.is_superadmin

            if request.POST.get('remember_me'):
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
            else:
                request.session.set_expiry(0)  # Session expires when browser closes
            
            return redirect('adminn:adminhome' if user.is_superadmin else 'home')
        else:
            messages.error(request, 'Invalid login credentials')
            return render(request, 'accounts/login.html')  

    return render(request, 'accounts/login.html')

@never_cache
@csrf_protect
def activate(request, uidb64, token):
    try:
        
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid) 
        
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True 
        user.save()  
        messages.success(request, 'Your account has been activated! You can now log in.')
        return redirect('login') 
    else:
        messages.error('Activation link is invalid!')
        return redirect('register')
    
@csrf_protect    
@never_cache   
def forgotPassword(request):
    if request.method == "POST":
        email = request.POST.get('email') 
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)

            current_site = get_current_site(request)
            mail_subject = 'Reset Password'
            message = render_to_string('accounts/reset_password_email.html', {
                'user': user,
                'domain': 'http://127.0.0.1:8000/',
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            messages.success(request, 'Password reset link has been sent to your email.')
            return redirect('login')  
        else:
            messages.error(request, 'Account with that email does not exist.')
            return redirect('forgotPassword') 

    return render(request, 'accounts/forgotPassword.html')

@never_cache
@csrf_protect
def resetpassword_validate(request, uidb64, token):
    try: 
        uid  = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist): user - None

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request,'Please reset your password') 
        return redirect('resetPassword')
    else:
        messages.error(request, 'This link has been expired!') 
        return redirect('login')
    
@csrf_protect    
@never_cache    
def resetPassword(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long!')
            return redirect('resetPassword')
        if not re.search(r"[A-Z]", password):
            messages.error(request, 'Password must contain at least one uppercase letter!')
            return redirect('resetPassword')
        if not re.search(r"[a-z]", password):
            messages.error(request, 'Password must contain at least one lowercase letter!')
            return redirect('resetPassword')
        if not re.search(r"[0-9]", password):
            messages.error(request, 'Password must contain at least one number!')
            return redirect('resetPassword')
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            messages.error(request, 'Password must contain at least one special character!')
            return redirect('resetPassword')
        
        if password == confirm_password:
            uid= request.session.get('uid')
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request,'Password reset successfull')
            return redirect('login') 
        else:
            messages.error(request,'Password do not match')
            return redirect('resetPassword')
    else:
        return render(request,'accounts/resetPassword.html')
    
@login_required(login_url='login')
def dashboard(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_at')
    orders_count = orders.count()
    
    context = {
        'orders_count': orders_count,
        'orders': orders[:5],  
    }
    return render(request, 'accounts/dashboard.html', context)

@login_required(login_url='login')
def my_orders(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_at')
    context = {
        'orders': orders,
    }
    return render(request, 'accounts/my_orders.html', context)

@login_required(login_url='login')
def edit_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = UserProfileForm(instance=request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'accounts/edit_profile.html', context)

@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password  successfully updated!')
            return redirect('dashboard')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'accounts/change_password.html', context)

@login_required(login_url='login')
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    ordered_products = OrderProduct.objects.filter(order=order)
    
    context = {
        'order': order,
        'ordered_products': ordered_products,
    }
    return render(request, 'accounts/order_detail.html', context)

@login_required(login_url='login')
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status == 'New':
        order.status = 'Cancelled'
        order.save()
      
        ordered_products = OrderProduct.objects.filter(order=order)
        for item in ordered_products:
            product = item.product
            product.stock += item.quantity
            product.save()
            
        messages.success(request, 'Order has been cancelled successfully.')
    else:
        messages.error(request, 'This order cannot be cancelled.')
    return redirect('order_detail', order_id=order_id)

@csrf_protect
@never_cache   
@login_required(login_url="login")
def logout(request):
    
    request.session.flush()
    auth.logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

@login_required
def manage_addresses(request):
    addresses = Address.objects.filter(user=request.user)
    context = {
        'addresses': addresses
    }
    return render(request, 'accounts/manage_addresses.html', context)

@login_required
def add_address(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        address_line_1 = request.POST.get('address_line_1')
        address_line_2 = request.POST.get('address_line_2', '')
        city = request.POST.get('city')
        state = request.POST.get('state')
        pincode = request.POST.get('pincode')
        is_default = request.POST.get('is_default') == 'on'

        address = Address(
            user=request.user,
            full_name=full_name,
            phone=phone,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            pincode=pincode,
            is_default=is_default
        )
        address.save()
        return redirect('manage_addresses')

@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        address.full_name = request.POST.get('full_name')
        address.phone = request.POST.get('phone')
        address.address_line_1 = request.POST.get('address_line_1')
        address.address_line_2 = request.POST.get('address_line_2', '')
        address.city = request.POST.get('city')
        address.state = request.POST.get('state')
        address.pincode = request.POST.get('pincode')
        address.save()
        
        messages.success(request, 'Address updated successfully.')
        return redirect('manage_addresses')

@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if not address.is_default:
        address.delete()
    else:
        messages.error(request, 'Cannot delete default address.')
    return redirect('manage_addresses')

@login_required
def set_default_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.is_default = True
    address.save()
    return redirect('manage_addresses')