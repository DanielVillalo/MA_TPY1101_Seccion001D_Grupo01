import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _columnas(schema_editor, tabla):
    with schema_editor.connection.cursor() as cursor:
        return {
            columna.name
            for columna in schema_editor.connection.introspection.get_table_description(
                cursor, tabla
            )
        }


def _es_esquema_heredado(schema_editor):
    tabla = "repuestosfullcars_compra"
    if tabla not in schema_editor.connection.introspection.table_names():
        return False
    return "webpay_token" in _columnas(schema_editor, tabla)


def _eliminar_indices_de_columna(schema_editor, tabla, columna):
    with schema_editor.connection.cursor() as cursor:
        restricciones = schema_editor.connection.introspection.get_constraints(
            cursor, tabla
        )
    for nombre, datos in restricciones.items():
        if datos.get("index") and columna in datos.get("columns", []):
            schema_editor.execute(
                f"DROP INDEX IF EXISTS {schema_editor.quote_name(nombre)}"
            )


def limpiar_columnas_de_pago_heredadas(apps, schema_editor):
    tabla = "repuestosfullcars_compra"
    if tabla not in schema_editor.connection.introspection.table_names():
        return

    columnas = _columnas(schema_editor, tabla)
    modelo = apps.get_model("repuestosfullcars", "Compra")
    for nombre in [
        "webpay_token",
        "webpay_buy_order",
        "webpay_session_id",
        "webpay_authorization_code",
        "stripe_checkout_session_id",
        "stripe_payment_status",
    ]:
        if nombre not in columnas:
            continue
        _eliminar_indices_de_columna(schema_editor, tabla, nombre)
        campo = models.CharField(max_length=255, blank=True)
        campo.set_attributes_from_name(nombre)
        campo.model = modelo
        schema_editor.remove_field(modelo, campo)
        columnas = _columnas(schema_editor, tabla)

    schema_editor.execute(
        f"UPDATE {schema_editor.quote_name(tabla)} "
        f"SET {schema_editor.quote_name('metodo_pago')} = %s",
        params=["sin_pago_en_linea"],
    )


class AddFieldIfNotExists(migrations.AddField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        modelo = to_state.apps.get_model(app_label, self.model_name)
        if self.name not in _columnas(schema_editor, modelo._meta.db_table):
            super().database_forwards(app_label, schema_editor, from_state, to_state)


class AlterFieldUnlessLegacy(migrations.AlterField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if not _es_esquema_heredado(schema_editor):
            super().database_forwards(app_label, schema_editor, from_state, to_state)


class CreateModelIfNotExists(migrations.CreateModel):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        modelo = to_state.apps.get_model(app_label, self.name)
        if modelo._meta.db_table not in schema_editor.connection.introspection.table_names():
            super().database_forwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    dependencies = [
        ("repuestosfullcars", "0003_rename_nombre_categoria_nombre_categoria_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="categoria",
            options={"ordering": ("nombre_categoria",)},
        ),
        migrations.AlterModelOptions(
            name="compra",
            options={"ordering": ("-fecha_compra",)},
        ),
        migrations.AlterModelOptions(
            name="producto",
            options={"ordering": ("nombre_producto",)},
        ),
        AddFieldIfNotExists(
            model_name="compra",
            name="fecha_actualizacion",
            field=models.DateTimeField(auto_now=True),
        ),
        AddFieldIfNotExists(
            model_name="compra",
            name="stock_descontado",
            field=models.BooleanField(default=False),
        ),
        AlterFieldUnlessLegacy(
            model_name="categoria",
            name="estado",
            field=models.CharField(
                choices=[("activo", "Activo"), ("inactivo", "Inactivo")],
                default="activo",
                max_length=10,
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="categoria",
            name="nombre_categoria",
            field=models.CharField(max_length=100, unique=True),
        ),
        AlterFieldUnlessLegacy(
            model_name="compra",
            name="estado_compra",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("anulada", "Anulada"),
                    ("entregada", "Entregada"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="compra",
            name="metodo_pago",
            field=models.CharField(default="sin_pago_en_linea", max_length=50),
        ),
        AlterFieldUnlessLegacy(
            model_name="compra",
            name="total",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="compra",
            name="usuario",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="compras",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="producto",
            name="categoria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="productos",
                to="repuestosfullcars.categoria",
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="producto",
            name="estado",
            field=models.CharField(
                choices=[("activo", "Activo"), ("inactivo", "Inactivo")],
                default="activo",
                max_length=10,
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="producto",
            name="imagen_url",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="productos/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ["jpg", "jpeg", "png", "webp"]
                    )
                ],
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="producto",
            name="precio",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        AlterFieldUnlessLegacy(
            model_name="producto",
            name="stock",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(
            limpiar_columnas_de_pago_heredadas,
            reverse_code=migrations.RunPython.noop,
        ),
        CreateModelIfNotExists(
            name="DetalleCompra",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre_producto", models.CharField(max_length=200)),
                (
                    "precio_unitario",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "cantidad",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                (
                    "subtotal",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "compra",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="detalles",
                        to="repuestosfullcars.compra",
                    ),
                ),
                (
                    "producto",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="detalles_compra",
                        to="repuestosfullcars.producto",
                    ),
                ),
            ],
        ),
        CreateModelIfNotExists(
            name="MovimientoStock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tipo",
                    models.CharField(
                        choices=[("entrada", "Entrada"), ("salida", "Salida")],
                        max_length=10,
                    ),
                ),
                (
                    "cantidad",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("stock_anterior", models.PositiveIntegerField()),
                ("stock_nuevo", models.PositiveIntegerField()),
                ("motivo", models.CharField(max_length=255)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                (
                    "compra",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="movimientos_stock",
                        to="repuestosfullcars.compra",
                    ),
                ),
                (
                    "producto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="movimientos_stock",
                        to="repuestosfullcars.producto",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-fecha",)},
        ),
    ]
