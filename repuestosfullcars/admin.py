from django.contrib import admin
from .models import Categoria, Producto

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    # Esto define qué columnas verás en la tabla del admin
    list_display = ('nombre', 'precio', 'stock', 'marca', 'categoria')
    # Esto añade un buscador por nombre o SKU
    search_fields = ('nombre', 'sku')
    # Esto añade filtros laterales por marca y categoría
    list_filter = ('marca', 'categoria')

admin.site.register(Categoria)