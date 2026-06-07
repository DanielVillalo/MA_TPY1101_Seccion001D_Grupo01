from decimal import Decimal

from .models import Producto


CARRITO_KEY = "carrito"


def obtener(request):
    return request.session.get(CARRITO_KEY, {})


def guardar(request, carrito):
    request.session[CARRITO_KEY] = carrito
    request.session.modified = True


def agregar(request, producto, cantidad=1):
    carrito = obtener(request)
    clave = str(producto.pk)
    actual = int(carrito.get(clave, 0))
    carrito[clave] = min(producto.stock, actual + max(1, int(cantidad)))
    guardar(request, carrito)


def actualizar(request, producto, cantidad):
    carrito = obtener(request)
    clave = str(producto.pk)
    cantidad = max(0, min(producto.stock, int(cantidad)))
    if cantidad:
        carrito[clave] = cantidad
    else:
        carrito.pop(clave, None)
    guardar(request, carrito)


def quitar(request, producto_id):
    carrito = obtener(request)
    carrito.pop(str(producto_id), None)
    guardar(request, carrito)


def vaciar(request):
    guardar(request, {})


def resumen(request):
    carrito = obtener(request)
    ids = [int(producto_id) for producto_id in carrito if producto_id.isdigit()]
    productos = Producto.objects.filter(pk__in=ids, estado="activo").select_related("categoria")
    lineas = []
    total = Decimal("0")
    cantidad_total = 0

    for producto in productos:
        cantidad = min(max(0, int(carrito.get(str(producto.pk), 0))), producto.stock)
        if not cantidad:
            continue
        subtotal = producto.precio * cantidad
        lineas.append({"producto": producto, "cantidad": cantidad, "subtotal": subtotal})
        total += subtotal
        cantidad_total += cantidad

    return {"lineas": lineas, "total": total, "cantidad_total": cantidad_total}
