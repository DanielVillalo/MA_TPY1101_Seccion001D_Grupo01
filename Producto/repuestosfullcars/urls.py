from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Ahora el index usa home.html
    path('', views.index, name='index'),
    
    # Apuntamos a la carpeta 'usuarios/' para el login
    path('login/', auth_views.LoginView.as_view(template_name='usuarios/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('registro/', views.registro, name='registro'),

    path('gestion-productos/', views.admin_productos, name='admin_productos'),
    path('eliminar-producto/<int:id>/', views.eliminar_producto, name='eliminar_producto'),
]