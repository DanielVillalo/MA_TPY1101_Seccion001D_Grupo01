from django.db import migrations, models


def _columnas(schema_editor, tabla):
    with schema_editor.connection.cursor() as cursor:
        return {
            columna.name
            for columna in schema_editor.connection.introspection.get_table_description(
                cursor, tabla
            )
        }


def normalizar_movimientos(apps, schema_editor):
    tabla = "repuestosfullcars_movimientostock"
    if tabla not in schema_editor.connection.introspection.table_names():
        return

    modelo = apps.get_model("repuestosfullcars", "MovimientoStock")
    columnas = _columnas(schema_editor, tabla)
    schema_editor.execute(
        f"UPDATE {schema_editor.quote_name(tabla)} "
        f"SET {schema_editor.quote_name('tipo')} = %s, "
        f"{schema_editor.quote_name('cantidad')} = ABS({schema_editor.quote_name('cantidad')}) "
        f"WHERE {schema_editor.quote_name('tipo')} = %s",
        params=["salida", "venta"],
    )
    schema_editor.execute(
        f"UPDATE {schema_editor.quote_name(tabla)} "
        f"SET {schema_editor.quote_name('tipo')} = %s, "
        f"{schema_editor.quote_name('cantidad')} = ABS({schema_editor.quote_name('cantidad')}) "
        f"WHERE {schema_editor.quote_name('tipo')} = %s",
        params=["entrada", "anulacion"],
    )

    if "usuario_id" not in columnas:
        schema_editor.add_field(modelo, modelo._meta.get_field("usuario"))
        columnas = _columnas(schema_editor, tabla)
    if "motivo" not in columnas:
        campo = models.CharField(max_length=255, default="", blank=True)
        campo.set_attributes_from_name("motivo")
        campo.model = modelo
        schema_editor.add_field(modelo, campo)

    schema_editor.execute(
        f"UPDATE {schema_editor.quote_name(tabla)} "
        f"SET {schema_editor.quote_name('motivo')} = %s "
        f"WHERE {schema_editor.quote_name('tipo')} = %s "
        f"AND {schema_editor.quote_name('motivo')} = %s",
        params=["Creacion de pedido", "salida", ""],
    )
    schema_editor.execute(
        f"UPDATE {schema_editor.quote_name(tabla)} "
        f"SET {schema_editor.quote_name('motivo')} = %s "
        f"WHERE {schema_editor.quote_name('tipo')} = %s "
        f"AND {schema_editor.quote_name('motivo')} = %s",
        params=["Anulacion de pedido", "entrada", ""],
    )


class Migration(migrations.Migration):
    dependencies = [
        (
            "repuestosfullcars",
            "0004_compra_fecha_actualizacion_compra_stock_descontado_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            normalizar_movimientos,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
