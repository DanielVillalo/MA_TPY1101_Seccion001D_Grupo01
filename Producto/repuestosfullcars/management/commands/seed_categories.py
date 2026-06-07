from django.core.management.base import BaseCommand

from repuestosfullcars.models import Categoria


class Command(BaseCommand):
    help = "Crea las categorias iniciales requeridas por el inventario."

    def handle(self, *args, **options):
        categorias = [
            ("Aceites", "Lubricantes y aceites para el cuidado del motor."),
            ("Electricidad", "Componentes electricos para el vehiculo."),
            ("Filtros", "Filtros de aire, aceite y combustible."),
            ("Frenos", "Repuestos para el sistema de frenado."),
            ("Motor", "Componentes y accesorios para el motor."),
            ("Suspension", "Repuestos para suspension y direccion."),
        ]
        creadas = 0
        for nombre, descripcion in categorias:
            _, creada = Categoria.objects.get_or_create(
                nombre_categoria=nombre,
                defaults={"descripcion": descripcion, "estado": "activo"},
            )
            creadas += int(creada)
        self.stdout.write(self.style.SUCCESS(f"Categorias listas. Nuevas: {creadas}"))
