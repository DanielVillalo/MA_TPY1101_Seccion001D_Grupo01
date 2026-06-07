from django.contrib import admin

from .models import Categoria, Compra, DetalleCompra, MovimientoStock, Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre_producto", "categoria", "precio", "stock", "estado")
    list_filter = ("categoria", "estado")
    search_fields = ("nombre_producto",)


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 0
    readonly_fields = ("nombre_producto", "precio_unitario", "cantidad", "subtotal")


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "total", "estado_compra", "fecha_compra")
    list_filter = ("estado_compra",)
    inlines = [DetalleCompraInline]


admin.site.register(Categoria)
admin.site.register(MovimientoStock)
