from django.contrib import admin
from .models import Categoria, Producto, Compra

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    # Usamos los nombres exactos de los campos en models.py
    list_display = ('nombre_producto', 'categoria', 'precio', 'stock', 'estado')
    list_filter = ('categoria', 'estado')
    search_fields = ('nombre_producto',)

admin.site.register(Categoria)
admin.site.register(Compra)