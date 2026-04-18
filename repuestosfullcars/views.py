from django.shortcuts import render
from .models import Producto

def home(request):
    # Aunque no tengas datos, esto debe existir para que la URL funcione
    productos = Producto.objects.all()
    return render(request, 'repuestosfullcars/index.html', {'productos': productos})