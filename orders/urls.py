from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    path('place_order/', views.place_order, name='place_order'),
    path('get_states/', views.get_states, name='get_states'),
    path('get_cities/', views.get_cities, name='get_cities'),
    path('payments/', views.payments, name='payments'),
    path('wallet_payment/', views.wallet_payment, name='wallet_payment'),
    path('cash_on_delivery/<str:order_number>/', views.cash_on_delivery, name='cash_on_delivery'),
    path('confirm_cod/<str:order_number>/', views.confirm_cod, name='confirm_cod'),
    path('order_complete/', views.order_complete, name='order_complete'),
]