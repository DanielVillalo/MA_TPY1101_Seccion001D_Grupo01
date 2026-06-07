from django.db import transaction

from .models import Compra, DetalleCompra, MovimientoStock, Producto


class StockInsuficiente(Exception):
    pass


@transaction.atomic
def crear_pedido(usuario, direccion_envio, lineas, total):
    productos = {
        producto.pk: producto
        for producto in Producto.objects.select_for_update().filter(
            pk__in=[linea["producto"].pk for linea in lineas]
        )
    }

    for linea in lineas:
        producto = productos.get(linea["producto"].pk)
        if not producto or producto.estado != "activo" or producto.stock < linea["cantidad"]:
            raise StockInsuficiente(linea["producto"].nombre_producto)

    compra = Compra.objects.create(
        usuario=usuario,
        total=total,
        direccion_envio=direccion_envio,
        stock_descontado=True,
    )

    for linea in lineas:
        producto = productos[linea["producto"].pk]
        anterior = producto.stock
        producto.stock -= linea["cantidad"]
        producto.save(update_fields=["stock", "fecha_actualizacion"])
        DetalleCompra.objects.create(
            compra=compra,
            producto=producto,
            nombre_producto=producto.nombre_producto,
            precio_unitario=producto.precio,
            cantidad=linea["cantidad"],
            subtotal=linea["subtotal"],
        )
        MovimientoStock.objects.create(
            producto=producto,
            compra=compra,
            usuario=usuario,
            tipo=MovimientoStock.TIPO_SALIDA,
            cantidad=linea["cantidad"],
            stock_anterior=anterior,
            stock_nuevo=producto.stock,
            motivo=f"Creacion de pedido #{compra.pk}",
        )
    return compra


@transaction.atomic
def anular_compra(compra_id, usuario=None):
    compra = Compra.objects.select_for_update().get(pk=compra_id)
    if compra.estado_compra == Compra.ESTADO_ANULADA:
        return compra
    if compra.estado_compra == Compra.ESTADO_ENTREGADA:
        return compra

    if compra.stock_descontado:
        detalles = list(compra.detalles.select_related("producto"))
        productos = {
            producto.pk: producto
            for producto in Producto.objects.select_for_update().filter(
                pk__in=[detalle.producto_id for detalle in detalles if detalle.producto_id]
            )
        }
        for detalle in detalles:
            producto = productos.get(detalle.producto_id)
            if not producto:
                continue
            anterior = producto.stock
            producto.stock += detalle.cantidad
            producto.save(update_fields=["stock", "fecha_actualizacion"])
            MovimientoStock.objects.create(
                producto=producto,
                compra=compra,
                usuario=usuario,
                tipo=MovimientoStock.TIPO_ENTRADA,
                cantidad=detalle.cantidad,
                stock_anterior=anterior,
                stock_nuevo=producto.stock,
                motivo=f"Anulacion de pedido #{compra.pk}",
            )
        compra.stock_descontado = False

    compra.estado_compra = Compra.ESTADO_ANULADA
    compra.save(update_fields=["estado_compra", "stock_descontado", "fecha_actualizacion"])
    return compra
