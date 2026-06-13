from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("repuestosfullcars", "0005_normalizar_esquema_de_pedidos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="compra",
            name="estado_compra",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente de pago"),
                    ("pagada", "Pagada"),
                    ("rechazada", "Pago rechazado"),
                    ("anulada", "Anulada"),
                    ("entregada", "Entregada"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
    ]
