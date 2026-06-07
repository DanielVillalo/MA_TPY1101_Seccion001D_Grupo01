import unicodedata

from django.urls import reverse

from .models import Categoria, Producto


PALABRAS_IGNORADAS = {
    "algo",
    "algun",
    "alguna",
    "ayuda",
    "buscar",
    "busco",
    "con",
    "de",
    "del",
    "disponible",
    "disponibles",
    "el",
    "en",
    "favor",
    "hay",
    "la",
    "las",
    "los",
    "me",
    "mostrar",
    "necesito",
    "para",
    "por",
    "producto",
    "productos",
    "puedes",
    "que",
    "quiero",
    "repuesto",
    "repuestos",
    "stock",
    "tienen",
    "tienes",
    "un",
    "una",
    "ver",
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def _contiene(texto, *terminos):
    return any(termino in texto for termino in terminos)


def _precio_clp(precio):
    return f"${precio:,.0f}".replace(",", ".")


def _producto_json(producto):
    return {
        "nombre": producto.nombre_producto,
        "categoria": producto.categoria.nombre_categoria,
        "precio": _precio_clp(producto.precio),
        "stock": producto.stock,
        "url": reverse("producto_detalle", args=[producto.pk]),
    }


def _buscar_productos(texto, mostrar_todos=False):
    palabras = {
        palabra
        for palabra in _normalizar(texto).replace("?", " ").replace(",", " ").split()
        if len(palabra) >= 3 and palabra not in PALABRAS_IGNORADAS
    }
    if not palabras and not mostrar_todos:
        return []

    productos = Producto.objects.filter(
        estado="activo",
        categoria__estado="activo",
        stock__gt=0,
    ).select_related("categoria")

    if palabras:
        productos = [
            producto
            for producto in productos
            if any(
                palabra
                in _normalizar(
                    f"{producto.nombre_producto} {producto.descripcion or ''} "
                    f"{producto.categoria.nombre_categoria}"
                )
                for palabra in palabras
            )
        ]
    else:
        productos = list(productos)
    return [_producto_json(producto) for producto in productos[:3]]


def responder(pregunta, usuario=None):
    texto = _normalizar(pregunta.strip())

    if _contiene(texto, "hola", "buenas", "buen dia"):
        return {
            "respuesta": (
                "Hola. Puedo ayudarte a encontrar repuestos disponibles o responder "
                "preguntas sobre carrito, pedidos y recuperación de contraseña."
            )
        }
    if _contiene(texto, "ayuda", "que puedes hacer", "como funciona"):
        return {
            "respuesta": (
                "Puedo buscar repuestos con stock y responder dudas sobre categorías, "
                "carrito, pedidos, despacho, contacto y recuperación de contraseña."
            )
        }
    if _contiene(texto, "contrasena", "clave", "recuperar cuenta"):
        return {
            "respuesta": (
                "Para recuperar tu contraseña, abre Iniciar sesión y selecciona "
                "¿Olvidaste tu contraseña? Te enviaremos un enlace al correo registrado."
            )
        }
    if _contiene(texto, "carrito", "agregar", "anadir"):
        return {
            "respuesta": (
                "Abre el repuesto que te interese y pulsa Añadir al carrito. "
                "Desde el icono del carrito puedes ajustar cantidades y confirmar el pedido."
            )
        }
    if _contiene(texto, "pedido", "pedidos", "compra", "seguimiento", "estado"):
        if usuario and usuario.is_authenticated:
            respuesta = (
                "Puedes revisar el estado y detalle de tus pedidos desde el icono "
                "de recibo ubicado en la barra superior."
            )
        else:
            respuesta = (
                "Inicia sesión para confirmar pedidos y revisar su estado desde "
                "el icono de recibo ubicado en la barra superior."
            )
        return {"respuesta": respuesta}
    if _contiene(texto, "despacho", "envio", "entrega", "direccion"):
        return {
            "respuesta": (
                "Al confirmar el pedido debes indicar una dirección de envío. "
                "Luego el equipo administrador gestiona su entrega."
            )
        }
    if _contiene(texto, "contacto", "contactar", "soporte", "administrador"):
        return {
            "respuesta": (
                "Puedes encontrar la información de contacto al final de la página. "
                "Desplázate hasta la sección Contacto."
            )
        }

    categorias = list(
        Categoria.objects.filter(estado="activo")
        .values_list("nombre_categoria", flat=True)
        .order_by("nombre_categoria")
    )
    if _contiene(texto, "categoria", "categorias", "que venden", "catalogo"):
        if categorias:
            return {
                "respuesta": "Actualmente puedes explorar estas categorías: "
                + ", ".join(categorias)
                + ". También puedes preguntarme por un repuesto específico."
            }
        return {"respuesta": "Todavía no hay categorías disponibles en el catálogo."}

    productos = _buscar_productos(
        texto,
        mostrar_todos=_contiene(texto, "stock", "disponible", "repuestos"),
    )
    if productos:
        return {
            "respuesta": "Encontré estas opciones disponibles en el catálogo:",
            "productos": productos,
        }
    return {
        "respuesta": (
            "No encontré un repuesto disponible con ese término. Prueba con el nombre "
            "de una pieza o pregúntame por categorías, pedidos, carrito o contraseña."
        )
    }
