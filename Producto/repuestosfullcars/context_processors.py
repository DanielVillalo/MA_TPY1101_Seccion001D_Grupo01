from django.conf import settings

from .carrito import resumen


def carrito_contexto(request):
    if not request.user.is_authenticated:
        cantidad = 0
    else:
        cantidad = resumen(request)["cantidad_total"]
    return {
        "carrito_cantidad": cantidad,
        "google_oauth_enabled": settings.GOOGLE_OAUTH_ENABLED,
    }
