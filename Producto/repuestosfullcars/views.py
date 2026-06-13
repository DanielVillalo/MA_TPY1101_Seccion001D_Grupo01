import json
from decimal import Decimal, InvalidOperation

import mercadopago
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import carrito
from .asistente import responder
from .forms import CheckoutForm, ProductoForm, RegistroForm
from .models import Categoria, Compra, Producto
from .servicios import StockInsuficiente, anular_compra, crear_pedido, rechazar_compra


@method_decorator(never_cache, name="dispatch")
class LoginSeguroView(LoginView):
    template_name = "usuarios/login.html"


@require_POST
@never_cache
def asistente_responder(request):
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Envía una pregunta válida."}, status=400)

    pregunta = str(datos.get("pregunta", "")).strip()
    if not pregunta:
        return JsonResponse({"error": "Escribe una pregunta para continuar."}, status=400)
    if len(pregunta) > 200:
        return JsonResponse({"error": "La pregunta no puede superar los 200 caracteres."}, status=400)
    return JsonResponse(responder(pregunta, usuario=request.user))


def _retorno_seguro(request, fallback="index"):
    retorno = request.POST.get("next", "")
    if retorno and url_has_allowed_host_and_scheme(
        retorno,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return retorno
    return reverse(fallback)


def index(request):
    categorias = Categoria.objects.filter(estado="activo").order_by("nombre_categoria")
    productos = Producto.objects.filter(estado="activo", categoria__estado="activo").select_related("categoria")
    categoria_filtro = request.GET.get("categoria")
    busqueda = request.GET.get("q", "").strip()

    if categoria_filtro and categoria_filtro.isdigit():
        productos = productos.filter(categoria_id=int(categoria_filtro))
    if busqueda:
        productos = productos.filter(
            Q(nombre_producto__icontains=busqueda)
            | Q(descripcion__icontains=busqueda)
            | Q(categoria__nombre_categoria__icontains=busqueda)
        )

    categorias_con_productos = []
    for categoria in categorias:
        productos_categoria = list(productos.filter(categoria=categoria))
        if productos_categoria:
            categorias_con_productos.append({"categoria": categoria, "productos": productos_categoria})

    return render(
        request,
        "repuestosfullcars/home.html",
        {
            "categorias_con_productos": categorias_con_productos,
            "categorias": categorias,
            "categoria_filtro": categoria_filtro,
            "busqueda": busqueda,
        },
    )


def producto_detalle(request, producto_id):
    producto = get_object_or_404(
        Producto.objects.select_related("categoria"),
        pk=producto_id,
        estado="activo",
        categoria__estado="activo",
    )
    return render(request, "repuestosfullcars/producto_detalle.html", {"producto": producto})


@never_cache
def registro(request):
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        messages.success(request, f"Bienvenido {usuario.username}. Ya puedes iniciar sesión.")
        return redirect("login")

    return render(request, "usuarios/registro.html", {"form": form})


@require_POST
def agregar_carrito(request, producto_id):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={_retorno_seguro(request)}")
    producto = get_object_or_404(Producto, pk=producto_id, estado="activo", categoria__estado="activo")
    if producto.stock <= 0:
        messages.error(request, "Este producto no tiene stock disponible.")
    else:
        try:
            cantidad = max(1, int(request.POST.get("cantidad", "1")))
        except ValueError:
            cantidad = 1
        cantidad = min(cantidad, producto.stock)
        carrito.agregar(request, producto, cantidad)
        messages.success(
            request,
            f"Agregaste {cantidad} unidad(es) de '{producto.nombre_producto}' al carrito.",
        )
    return redirect(_retorno_seguro(request))


@never_cache
def ver_carrito(request):
    return render(request, "repuestosfullcars/carrito.html", carrito.resumen(request))


@require_POST
def actualizar_carrito(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id, estado="activo")
    try:
        cantidad = int(request.POST.get("cantidad", "1"))
    except ValueError:
        cantidad = 1
    carrito.actualizar(request, producto, cantidad)
    return redirect("carrito")


@require_POST
def quitar_carrito(request, producto_id):
    carrito.quitar(request, producto_id)
    return redirect("carrito")


@never_cache
def checkout(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    resumen = carrito.resumen(request)
    if not resumen["lineas"]:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("carrito")

    form = CheckoutForm(
        request.POST or None,
        initial={
            "nombre_receptor": request.user.get_full_name() or request.user.username,
        },
    )
    if request.method == "POST" and form.is_valid():
        mercado_pago_configurado = bool(
            settings.MERCADOPAGO_ACCESS_TOKEN and settings.MERCADOPAGO_PUBLIC_KEY
        )
        if not settings.DEBUG and not mercado_pago_configurado:
            messages.error(
                request,
                "El pago en línea no está disponible. Intenta nuevamente más tarde.",
            )
            return render(
                request,
                "repuestosfullcars/checkout.html",
                {**resumen, "form": form},
                status=503,
            )

        try:
            compra = crear_pedido(
                usuario=request.user,
                direccion_envio=form.cleaned_data["direccion_envio"],
                lineas=resumen["lineas"],
                total=resumen["total"],
                nombre_receptor=form.cleaned_data["nombre_receptor"],
                telefono_contacto=form.cleaned_data["telefono_contacto"],
                comuna=form.cleaned_data["comuna"],
                ciudad=form.cleaned_data["ciudad"],
                referencia_entrega=form.cleaned_data["referencia_entrega"],
            )
        except StockInsuficiente:
            messages.error(request, "El stock cambió mientras confirmabas. Revisa tu carrito.")
            return redirect("carrito")

        carrito.vaciar(request)
        if not mercado_pago_configurado:
            compra.metodo_pago = "registro_local"
            compra.save(update_fields=["metodo_pago", "fecha_actualizacion"])
            messages.success(
                request,
                "Pedido registrado en modo local. Mercado Pago se activa al configurar sus claves.",
            )
            return redirect("compra_detalle", compra_id=compra.pk)
        return render(request, "repuestosfullcars/checkout_pago.html", {
            "compra": compra,
            "mp_public_key": settings.MERCADOPAGO_PUBLIC_KEY,
        })

    return render(request, "repuestosfullcars/checkout.html", {**resumen, "form": form})


@never_cache
def mis_compras(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    compras = Compra.objects.filter(usuario=request.user).order_by("-fecha_compra")
    return render(request, "repuestosfullcars/mis_compras.html", {"compras": compras})


@never_cache
def compra_detalle(request, compra_id):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    compra = get_object_or_404(Compra.objects.prefetch_related("detalles"), pk=compra_id)
    if compra.usuario_id != request.user.id and not request.user.is_staff:
        messages.error(request, "No tienes permiso para ver esta compra.")
        return redirect("mis_compras")
    return render(request, "repuestosfullcars/compra_detalle.html", {"compra": compra})


@staff_member_required
@never_cache
def admin_productos(request):
    producto_edit = None
    categorias = Categoria.objects.filter(estado="activo").order_by("nombre_categoria")
    busqueda = request.GET.get("q", "").strip()
    edit_id = request.GET.get("edit")
    if edit_id:
        producto_edit = get_object_or_404(Producto, pk=edit_id)

    form = ProductoForm(instance=producto_edit)
    if request.method == "POST":
        producto_edit = get_object_or_404(Producto, pk=request.POST.get("producto_id")) if request.POST.get("producto_id") else None
        form = ProductoForm(request.POST, request.FILES, instance=producto_edit)
        if form.is_valid():
            producto = form.save()
            accion = "actualizado" if producto_edit else "agregado al inventario"
            messages.success(request, f"Producto '{producto.nombre_producto}' {accion}.")
            return redirect("admin_productos")
        messages.error(request, "Revisa los datos: el precio y el stock no pueden ser negativos.")

    inventario = Producto.objects.select_related("categoria").order_by("-fecha_actualizacion")
    estadisticas = {
        "total": inventario.count(),
        "activos": inventario.filter(estado="activo").count(),
        "stock_bajo": inventario.filter(estado="activo", stock__gt=0, stock__lte=5).count(),
        "sin_stock": inventario.filter(estado="activo", stock=0).count(),
    }
    productos = inventario
    if busqueda:
        productos = productos.filter(
            Q(nombre_producto__icontains=busqueda)
            | Q(categoria__nombre_categoria__icontains=busqueda)
        )
    return render(
        request,
        "repuestosfullcars/admin_productos.html",
        {
            "productos": productos,
            "categorias": categorias,
            "producto_edit": producto_edit,
            "form": form,
            "busqueda": busqueda,
            "estadisticas": estadisticas,
        },
    )


@staff_member_required
@require_POST
def eliminar_producto(request, id):
    producto = get_object_or_404(Producto, pk=id)
    producto.estado = "inactivo"
    producto.save(update_fields=["estado", "fecha_actualizacion"])
    messages.warning(request, f"El producto '{producto.nombre_producto}' fue desactivado.")
    return redirect("admin_productos")


@staff_member_required
@never_cache
def admin_categorias(request):
    categoria_edit = None
    edit_id = request.GET.get("edit")
    if edit_id:
        categoria_edit = get_object_or_404(Categoria, pk=edit_id)

    if request.method == "POST":
        nombre = request.POST.get("nombre_categoria", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        estado = request.POST.get("estado", "activo")
        categoria_id = request.POST.get("categoria_id")
        if not nombre or estado not in {"activo", "inactivo"}:
            messages.error(request, "Completa correctamente los datos de la categoría.")
        else:
            categoria = get_object_or_404(Categoria, pk=categoria_id) if categoria_id else Categoria()
            categoria.nombre_categoria = nombre
            categoria.descripcion = descripcion
            categoria.estado = estado
            categoria.save()
            messages.success(request, f"Categoría '{nombre}' guardada.")
            return redirect("admin_categorias")

    categorias = Categoria.objects.order_by("nombre_categoria")
    return render(
        request,
        "repuestosfullcars/admin_categorias.html",
        {"categorias": categorias, "categoria_edit": categoria_edit},
    )


@staff_member_required
@never_cache
def admin_compras(request):
    if request.method == "POST":
        compra = get_object_or_404(Compra, pk=request.POST.get("compra_id"))
        accion = request.POST.get("accion")
        if accion == "anular":
            anular_compra(compra.pk, usuario=request.user)
            messages.success(request, f"Compra #{compra.pk} anulada.")
        elif accion == "entregar" and (
            compra.estado_compra == Compra.ESTADO_PAGADA
            or (
                compra.estado_compra == Compra.ESTADO_PENDIENTE
                and compra.metodo_pago == "registro_local"
            )
        ):
            compra.estado_compra = Compra.ESTADO_ENTREGADA
            compra.save(update_fields=["estado_compra", "fecha_actualizacion"])
            messages.success(request, f"Compra #{compra.pk} marcada como entregada.")

    compras = Compra.objects.select_related("usuario").prefetch_related("detalles").order_by("-fecha_compra")
    return render(request, "repuestosfullcars/admin_compras.html", {"compras": compras})

# Mercado Pago


def _sincronizar_pago(payment_id):
    if not payment_id or not settings.MERCADOPAGO_ACCESS_TOKEN:
        return None

    try:
        sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
        resultado = sdk.payment().get(payment_id)
    except Exception:
        return None
    if resultado.get("status") != 200:
        return None

    pago = resultado.get("response", {})
    compra = Compra.objects.filter(pk=pago.get("external_reference")).first()
    if not compra:
        return None

    try:
        monto = Decimal(str(pago.get("transaction_amount")))
    except (InvalidOperation, TypeError):
        return None
    if monto != compra.total:
        return None

    if pago.get("status") == "approved":
        if compra.estado_compra == Compra.ESTADO_RECHAZADA:
            return compra
        compra.estado_compra = Compra.ESTADO_PAGADA
        compra.metodo_pago = "mercado_pago"
        compra.save(
            update_fields=["estado_compra", "metodo_pago", "fecha_actualizacion"]
        )
    elif pago.get("status") in {"rejected", "cancelled"}:
        compra = rechazar_compra(compra.pk)
    return compra

@require_POST
def crear_preferencia_mp(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)
    if not settings.MERCADOPAGO_ACCESS_TOKEN:
        return JsonResponse(
            {"error": "Mercado Pago no está configurado en este ambiente."},
            status=503,
        )

    try:
        data = json.loads(request.body)
        compra_id = data.get("compra_id")

        compra = get_object_or_404(
            Compra.objects.prefetch_related("detalles__producto"),
            pk=compra_id,
            usuario=request.user,
        )

        sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

        items = [
            {
                "title":      detalle.nombre_producto,
                "quantity":   detalle.cantidad,
                "unit_price": float(detalle.precio_unitario),
                "currency_id": "CLP",
            }
            for detalle in compra.detalles.all()
        ]

        base_url = request.build_absolute_uri("/").rstrip("/")

        preference_data = {
            "items": items,
            "back_urls": {
                "success": f"{base_url}/pago/exitoso/{compra.pk}/",
                "failure": f"{base_url}/pago/fallido/{compra.pk}/",
                "pending": f"{base_url}/pago/pendiente/{compra.pk}/",
            },
            "notification_url": f"{base_url}/webhook/mp/",
            "external_reference": str(compra.pk),
        }

        # auto_return solo en producción
        if not settings.DEBUG:
            preference_data["auto_return"] = "approved"

        resultado = sdk.preference().create(preference_data)

        if resultado.get("status") == 201:
            respuesta = resultado.get("response", {})
            return JsonResponse({
                "preference_id": respuesta.get("id"),
                "init_point": respuesta.get("sandbox_init_point") or respuesta.get("init_point"),
            })
        return JsonResponse(
            {"error": "Mercado Pago no pudo crear la preferencia."},
            status=400,
        )

    except Exception:
        return JsonResponse({"error": "No fue posible iniciar el pago."}, status=400)


@csrf_exempt
def webhook_mp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            if data.get("type") == "payment":
                _sincronizar_pago(data.get("data", {}).get("id"))
        except (json.JSONDecodeError, KeyError, TypeError):
            return JsonResponse({"status": "invalid"}, status=400)
    return JsonResponse({"status": "ok"})


@never_cache
def pago_exitoso(request, compra_id):
    if not request.user.is_authenticated:
        return redirect("login")
    compra = get_object_or_404(Compra, pk=compra_id, usuario=request.user)
    compra_actualizada = _sincronizar_pago(request.GET.get("payment_id"))
    if compra_actualizada and compra_actualizada.estado_compra == Compra.ESTADO_PAGADA:
        messages.success(request, f"Pago del pedido #{compra.pk} aprobado.")
    else:
        messages.info(request, "El pago está siendo confirmado por Mercado Pago.")
    return redirect("compra_detalle", compra_id=compra.pk)


@never_cache
def pago_fallido(request, compra_id):
    if not request.user.is_authenticated:
        return redirect("login")
    compra = get_object_or_404(Compra, pk=compra_id, usuario=request.user)
    compra_actualizada = _sincronizar_pago(request.GET.get("payment_id"))
    if compra_actualizada and compra_actualizada.estado_compra == Compra.ESTADO_RECHAZADA:
        messages.error(request, f"El pago del pedido #{compra.pk} fue rechazado.")
    else:
        messages.warning(request, "Mercado Pago no confirmó el pago.")
    return redirect("compra_detalle", compra_id=compra.pk)


@never_cache
def pago_pendiente(request, compra_id):
    if not request.user.is_authenticated:
        return redirect("login")
    compra = get_object_or_404(Compra, pk=compra_id, usuario=request.user)
    _sincronizar_pago(request.GET.get("payment_id"))
    messages.warning(request, f"Pedido #{compra.pk} pendiente de confirmación.")
    return redirect("compra_detalle", compra_id=compra.pk)
