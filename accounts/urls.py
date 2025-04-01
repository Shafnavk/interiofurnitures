from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('my_orders/', views.my_orders, name='my_orders'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('change_password/', views.change_password, name='change_password'),
    path('order_detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('track_order/<int:order_id>/', views.track_order, name='track_order'),
    path('cancel_order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('login/google/', views.login_with_google, name='google_login'),
    path('login/google/callback/', views.google_callback, name='google_callback'),
    path('activate/<uidb64>/<token>', views.activate, name='activate'),
    path('forgotPassword/', views.forgotPassword, name='forgotPassword'),
    path('resetpassword_validate/<uidb64>/<token>', views.resetpassword_validate, name='resetpassword_validate'),
    path('resetPassword', views.resetPassword, name='resetPassword'), 
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('manage_addresses/', views.manage_addresses, name='manage_addresses'),
    path('add_address/', views.add_address, name='add_address'),
    path('edit_address/<int:address_id>/', views.edit_address, name='edit_address'),
    path('delete_address/<int:address_id>/', views.delete_address, name='delete_address'),
    path('set_default_address/<int:address_id>/', views.set_default_address, name='set_default_address'), 
    path('request-refund/<int:order_id>/', views.request_refund, name='request_refund'),
    path('my-wallet/', views.my_wallet, name='my_wallet'), 
]