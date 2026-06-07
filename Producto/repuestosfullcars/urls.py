from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.decorators.cache import never_cache

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("asistente/responder/", views.asistente_responder, name="asistente_responder"),
    path("producto/<int:producto_id>/", views.producto_detalle, name="producto_detalle"),
    path("login/", views.LoginSeguroView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("registro/", views.registro, name="registro"),
    path("carrito/", views.ver_carrito, name="carrito"),
    path("carrito/agregar/<int:producto_id>/", views.agregar_carrito, name="agregar_carrito"),
    path("carrito/actualizar/<int:producto_id>/", views.actualizar_carrito, name="actualizar_carrito"),
    path("carrito/quitar/<int:producto_id>/", views.quitar_carrito, name="quitar_carrito"),
    path("checkout/", views.checkout, name="checkout"),
    path("mis-compras/", views.mis_compras, name="mis_compras"),
    path("mis-compras/<int:compra_id>/", views.compra_detalle, name="compra_detalle"),
    path("gestion-productos/", views.admin_productos, name="admin_productos"),
    path("eliminar-producto/<int:id>/", views.eliminar_producto, name="eliminar_producto"),
    path("gestion-categorias/", views.admin_categorias, name="admin_categorias"),
    path("gestion-compras/", views.admin_compras, name="admin_compras"),
    path(
        "password-reset/",
        never_cache(
            auth_views.PasswordResetView.as_view(
                template_name="usuarios/password_reset.html",
                email_template_name="usuarios/password_reset_email.html",
                subject_template_name="usuarios/password_reset_subject.txt",
                success_url="/password-reset/done/",
            )
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        never_cache(auth_views.PasswordResetDoneView.as_view(template_name="usuarios/password_reset_done.html")),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        never_cache(
            auth_views.PasswordResetConfirmView.as_view(
                template_name="usuarios/password_reset_confirm.html",
                success_url="/password-reset-complete/",
            )
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        never_cache(auth_views.PasswordResetCompleteView.as_view(template_name="usuarios/password_reset_complete.html")),
        name="password_reset_complete",
    ),
]
