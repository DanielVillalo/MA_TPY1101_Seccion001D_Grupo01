from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models


class Categoria(models.Model):
    ESTADOS = (("activo", "Activo"), ("inactivo", "Inactivo"))

    nombre_categoria = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="activo")

    class Meta:
        ordering = ("nombre_categoria",)

    def __str__(self):
        return self.nombre_categoria


class Producto(models.Model):
    ESTADOS = Categoria.ESTADOS

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="productos"
    )
    nombre_producto = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    imagen_url = models.ImageField(
        upload_to="productos/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    stock = models.PositiveIntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="activo")

    class Meta:
        ordering = ("nombre_producto",)

    def __str__(self):
        return self.nombre_producto


class Compra(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_ANULADA = "anulada"
    ESTADO_ENTREGADA = "entregada"
    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ANULADA, "Anulada"),
        (ESTADO_ENTREGADA, "Entregada"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="compras"
    )
    fecha_compra = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    total = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    estado_compra = models.CharField(
        max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE
    )
    metodo_pago = models.CharField(max_length=50, default="sin_pago_en_linea")
    direccion_envio = models.TextField()
    stock_descontado = models.BooleanField(default=False)

    class Meta:
        ordering = ("-fecha_compra",)

    def __str__(self):
        return f"Compra {self.id} - {self.usuario.username}"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detalles_compra",
    )
    nombre_producto = models.CharField(max_length=200)
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    def __str__(self):
        return f"{self.cantidad} x {self.nombre_producto}"


class MovimientoStock(models.Model):
    TIPO_ENTRADA = "entrada"
    TIPO_SALIDA = "salida"
    TIPOS = [
        (TIPO_ENTRADA, "Entrada"),
        (TIPO_SALIDA, "Salida"),
    ]

    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="movimientos_stock"
    )
    compra = models.ForeignKey(
        Compra,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_stock",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    stock_anterior = models.PositiveIntegerField()
    stock_nuevo = models.PositiveIntegerField()
    motivo = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha",)

    def __str__(self):
        return f"{self.producto} - {self.tipo}: {self.cantidad}"
