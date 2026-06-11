import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import carrito
from .asistente import responder
from .forms import CheckoutForm, ProductoForm
from .models import Categoria, Compra, Producto
from .servicios import StockInsuficiente, anular_compra, crear_pedido


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
        {"categorias_con_productos": categorias_con_productos},
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
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirmacion = request.POST.get("confirmPassword", "")

        if password != confirmacion:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, "usuarios/registro.html")
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "Este nombre de usuario ya existe.")
            return render(request, "usuarios/registro.html")
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Este correo ya está asociado a una cuenta.")
            return render(request, "usuarios/registro.html")

        usuario = User(username=username, email=email)
        try:
            password_validation.validate_password(password, usuario)
        except ValidationError as errores:
            for error in errores:
                messages.error(request, error)
            return render(request, "usuarios/registro.html")

        usuario.set_password(password)
        usuario.save()
        messages.success(request, f"¡Bienvenido {username}! Ya puedes iniciar sesión.")
        return redirect("login")

    return render(request, "usuarios/registro.html")


@require_POST
def agregar_carrito(request, producto_id):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={_retorno_seguro(request)}")
    producto = get_object_or_404(Producto, pk=producto_id, estado="activo", categoria__estado="activo")
    if producto.stock <= 0:
        messages.error(request, "Este producto no tiene stock disponible.")
    else:
        carrito.agregar(request, producto)
        messages.success(request, f"Agregaste '{producto.nombre_producto}' al carrito.")
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

    form = CheckoutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            compra = crear_pedido(
                usuario=request.user,
                direccion_envio=form.cleaned_data["direccion_envio"],
                lineas=resumen["lineas"],
                total=resumen["total"],
            )
        except StockInsuficiente:
            messages.error(request, "El stock cambió mientras confirmabas. Revisa tu carrito.")
            return redirect("carrito")

        # ✅ Esto va FUERA del except, al mismo nivel que el try
        carrito.vaciar(request)
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
    edit_id = request.GET.get("edit")
    if edit_id:
        producto_edit = get_object_or_404(Producto, pk=edit_id)

    if request.method == "POST":
        producto_edit = get_object_or_404(Producto, pk=request.POST.get("producto_id")) if request.POST.get("producto_id") else None
        form = ProductoForm(request.POST, request.FILES, instance=producto_edit)
        if form.is_valid():
            producto = form.save()
            accion = "actualizado" if producto_edit else "agregado al inventario"
            messages.success(request, f"Producto '{producto.nombre_producto}' {accion}.")
            return redirect("admin_productos")
        messages.error(request, "Revisa los datos: el precio y el stock no pueden ser negativos.")

    productos = Producto.objects.select_related("categoria").order_by("-fecha_actualizacion")
    return render(
        request,
        "repuestosfullcars/admin_productos.html",
        {"productos": productos, "categorias": categorias, "producto_edit": producto_edit},
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
        elif accion == "entregar" and compra.estado_compra == Compra.ESTADO_PENDIENTE:
            compra.estado_compra = Compra.ESTADO_ENTREGADA
            compra.save(update_fields=["estado_compra", "fecha_actualizacion"])
            messages.success(request, f"Compra #{compra.pk} marcada como entregada.")

    compras = Compra.objects.select_related("usuario").prefetch_related("detalles").order_by("-fecha_compra")
    return render(request, "repuestosfullcars/admin_compras.html", {"compras": compras})

# ── Mercado Pago ──────────────────────────────────────────────
import mercadopago
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

@require_POST
def crear_preferencia_mp(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

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
            "external_reference": str(compra.pk),
        }

        # auto_return solo en producción
        if not settings.DEBUG:
            preference_data["auto_return"] = "approved"

        resultado = sdk.preference().create(preference_data)

        if resultado["status"] == 201:
            return JsonResponse({
                "preference_id": resultado["response"]["id"],
                "init_point": resultado["response"]["sandbox_init_point"],
            })

    except Exception as e:
        print(f"ERROR en crear_preferencia_mp: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def webhook_mp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            if data.get("type") == "payment":
                payment_id = data["data"]["id"]
                sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
                pago = sdk.payment().get(payment_id)["response"]
                compra_id = pago.get("external_reference")
                if compra_id and pago["status"] == "approved":
                    compra = Compra.objects.get(pk=compra_id)
                    compra.estado_compra = Compra.ESTADO_PENDIENTE
                    compra.save(update_fields=["estado_compra", "fecha_actualizacion"])
        except Exception as e:
            print(f"Webhook error: {e}")
    return JsonResponse({"status": "ok"})


@never_cache
def pago_exitoso(request, compra_id):
    compra = get_object_or_404(Compra, pk=compra_id, usuario=request.user)
    messages.success(request, f"¡Pago del pedido #{compra.pk} aprobado!")
    return redirect("compra_detalle", compra_id=compra.pk)


@never_cache
def pago_fallido(request, compra_id):
    compra = get_object_or_404(Compra, pk=compra_id, usuario=request.user)
    messages.error(request, f"El pago del pedido #{compra.pk} falló. Intenta nuevamente.")
    return redirect("compra_detalle", compra_id=compra.pk)


@never_cache
def pago_pendiente(request, compra_id):
    compra = get_object_or_404(Compra, pk=compra_id, usuario=request.user)
    messages.warning(request, f"Pedido #{compra.pk} pendiente de confirmación.")
    return redirect("compra_detalle", compra_id=compra.pk)