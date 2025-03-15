from django.urls import include, path
from . import views

app_name = 'adminn'

urlpatterns = [
    path('adminhome/',views.adminhome, name='adminhome'),
    path('signout/',views.signout, name='signout'),
    path('users/', views.users, name='users'),
    path('blockuser/<int:user_id>/', views.blockuser, name='blockuser'),
    path('unblockuser/<int:user_id>/', views.unblockuser, name='unblockuser'),
    path('categorylist/', views.categorylist, name='categorylist'),
    path('productlist/', views.productlist, name='productlist'),
    path('addproduct/', views.addproduct, name='addproduct'),
    path('editproduct/<int:product_id>/', views.editproduct, name = 'editproduct'),
    path('deleteproduct/<int:product_id>/', views.deleteproduct, name = 'deleteproduct'),
    path('restore-product/<int:product_id>/', views.restore_product, name='restore_product'),
    path('permanent-delete-product/<int:product_id>/', views.permanent_delete_product, name='permanent_delete_product'),
    path('delete-product-image/<int:image_id>/', views.delete_product_image, name='delete_product_image'),
    path('addcategory/', views.addcategory, name='addcategory'),
    path('editcategory/<int:category_id>/', views.editcategory, name='editcategory'),
    path('deletecategory/<int:category_id>/', views.deletecategory, name='deletecategory'),
    path('restore-category/<int:category_id>/', views.restore_category, name='restore_category'),
    path('permanent-delete-category/<int:category_id>/', views.permanent_delete_category, name='permanent_delete_category'),
]