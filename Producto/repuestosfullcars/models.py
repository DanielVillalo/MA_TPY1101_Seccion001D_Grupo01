from django.db import models
from django.contrib.auth.models import User # Usaremos el usuario de Django para 'USUARIOS'

class Categoria(models.Model):
    nombre_categoria = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=10, default='activo')

    def __str__(self):
        return self.nombre_categoria

class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    nombre_producto = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    imagen_url = models.ImageField(upload_to='productos/', null=True, blank=True)
    stock = models.IntegerField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    estado = models.CharField(max_length=10, default='activo')

    def __str__(self):
        return self.nombre_producto

class Compra(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_compra = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    estado_compra = models.CharField(max_length=20, default='pendiente')
    metodo_pago = models.CharField(max_length=50)
    direccion_envio = models.TextField()

    def __str__(self):
        return f"Compra {self.id} - {self.usuario.username}"