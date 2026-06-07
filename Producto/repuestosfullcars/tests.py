from decimal import Decimal
import json

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Categoria, Compra, MovimientoStock, Producto


class BaseTestCase(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre_categoria="Aceites", estado="activo")
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre_producto="Aceite 10W40",
            descripcion="Aceite vegetal",
            precio=Decimal("12990"),
            stock=5,
            estado="activo",
        )
        self.usuario = User.objects.create_user("cliente", "cliente@example.com", "ClaveSegura123!")
        self.staff = User.objects.create_user("admin", "admin@example.com", "ClaveSegura123!", is_staff=True)


class CatalogoTests(BaseTestCase):
    def test_catalogo_muestra_producto_activo_y_animacion_original(self):
        respuesta = self.client.get(reverse("index"))
        self.assertContains(respuesta, "Aceite 10W40")
        self.assertContains(respuesta, "fa-spin")

    def test_catalogo_oculta_producto_inactivo(self):
        self.producto.estado = "inactivo"
        self.producto.save()
        respuesta = self.client.get(reverse("index"))
        self.assertNotContains(respuesta, "Aceite 10W40")

    def test_detalle_producto_no_expone_producto_inactivo(self):
        self.producto.estado = "inactivo"
        self.producto.save()
        respuesta = self.client.get(reverse("producto_detalle", args=[self.producto.pk]))
        self.assertEqual(respuesta.status_code, 404)


class CuentaTests(BaseTestCase):
    def test_google_no_aparece_sin_credenciales(self):
        respuesta = self.client.get(reverse("login"))
        self.assertNotContains(respuesta, "Continuar con Google")

    def test_registro_rechaza_password_debil(self):
        respuesta = self.client.post(
            reverse("registro"),
            {"username": "nuevo", "email": "nuevo@example.com", "password": "123", "confirmPassword": "123"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(username="nuevo").exists())

    def test_logout_requiere_post(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_recuperacion_no_revela_si_correo_existe(self):
        conocida = self.client.post(reverse("password_reset"), {"email": self.usuario.email})
        desconocida = self.client.post(reverse("password_reset"), {"email": "nadie@example.com"})
        self.assertEqual(conocida.status_code, 302)
        self.assertEqual(desconocida.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)


class CarritoYPedidoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_agregar_carrito_exige_post(self):
        respuesta = self.client.get(reverse("agregar_carrito", args=[self.producto.pk]))
        self.assertEqual(respuesta.status_code, 405)

    def test_agregar_carrito_sin_sesion_regresa_a_pagina_segura(self):
        self.client.logout()
        respuesta = self.client.post(
            reverse("agregar_carrito", args=[self.producto.pk]),
            {"next": "https://sitio-malicioso.example/"},
        )
        self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('index')}")

    def test_carrito_limita_cantidad_al_stock(self):
        self.client.post(reverse("agregar_carrito", args=[self.producto.pk]))
        self.client.post(reverse("actualizar_carrito", args=[self.producto.pk]), {"cantidad": 999})
        respuesta = self.client.get(reverse("carrito"))
        self.assertContains(respuesta, 'value="5"')

    def test_checkout_crea_pedido_y_descuenta_stock(self):
        self.client.post(reverse("agregar_carrito", args=[self.producto.pk]))
        respuesta = self.client.post(reverse("checkout"), {"direccion_envio": "Av. Siempre Viva 123"})
        compra = Compra.objects.get(usuario=self.usuario)
        self.producto.refresh_from_db()
        self.assertRedirects(respuesta, reverse("compra_detalle", args=[compra.pk]))
        self.assertEqual(compra.detalles.get().cantidad, 1)
        self.assertEqual(self.producto.stock, 4)
        self.assertTrue(compra.stock_descontado)
        self.assertEqual(MovimientoStock.objects.get().cantidad, 1)

    def test_otro_cliente_no_puede_ver_pedido(self):
        self.client.post(reverse("agregar_carrito", args=[self.producto.pk]))
        self.client.post(reverse("checkout"), {"direccion_envio": "Av. Siempre Viva 123"})
        compra = Compra.objects.get(usuario=self.usuario)
        otro = User.objects.create_user("otro", "otro@example.com", "ClaveSegura123!")
        self.client.force_login(otro)
        respuesta = self.client.get(reverse("compra_detalle", args=[compra.pk]))
        self.assertRedirects(respuesta, reverse("mis_compras"))


class AdministracionTests(BaseTestCase):
    def test_seed_categories_es_idempotente(self):
        call_command("seed_categories", verbosity=0)
        primera_cantidad = Categoria.objects.count()
        call_command("seed_categories", verbosity=0)
        self.assertEqual(Categoria.objects.count(), primera_cantidad)

    def test_staff_puede_crear_categoria(self):
        self.client.force_login(self.staff)
        respuesta = self.client.post(
            reverse("admin_categorias"),
            {"nombre_categoria": "Filtros", "descripcion": "Filtros varios", "estado": "activo"},
        )
        self.assertRedirects(respuesta, reverse("admin_categorias"))
        self.assertTrue(Categoria.objects.filter(nombre_categoria="Filtros").exists())

    def test_cliente_no_puede_acceder_a_inventario(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("admin_productos"))
        self.assertEqual(respuesta.status_code, 302)

    def test_desactivar_producto_requiere_post(self):
        self.client.force_login(self.staff)
        url = reverse("eliminar_producto", args=[self.producto.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.estado, "inactivo")

    def test_inventario_rechaza_stock_negativo(self):
        self.client.force_login(self.staff)
        respuesta = self.client.post(
            reverse("admin_productos"),
            {
                "nombre_producto": "Producto invalido",
                "descripcion": "",
                "precio": "1000",
                "stock": "-1",
                "categoria": str(self.categoria.pk),
                "estado": "activo",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Producto.objects.filter(nombre_producto="Producto invalido").exists())

    def test_anular_pedido_restaura_stock_una_sola_vez(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("agregar_carrito", args=[self.producto.pk]))
        self.client.post(reverse("checkout"), {"direccion_envio": "Av. Siempre Viva 123"})
        compra = Compra.objects.get(usuario=self.usuario)
        self.client.force_login(self.staff)
        url = reverse("admin_compras")
        self.client.post(url, {"compra_id": compra.pk, "accion": "anular"})
        self.client.post(url, {"compra_id": compra.pk, "accion": "anular"})
        self.producto.refresh_from_db()
        compra.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)
        self.assertEqual(compra.estado_compra, Compra.ESTADO_ANULADA)
        self.assertEqual(MovimientoStock.objects.filter(tipo=MovimientoStock.TIPO_ENTRADA).count(), 1)


class CacheTests(BaseTestCase):
    def test_login_y_carrito_privado_no_se_cachean(self):
        self.client.force_login(self.usuario)
        self.assertIn("no-cache", self.client.get(reverse("login"))["Cache-Control"])
        self.assertIn("no-cache", self.client.get(reverse("carrito"))["Cache-Control"])


class AsistenteTests(BaseTestCase):
    def _preguntar(self, pregunta):
        return self.client.post(
            reverse("asistente_responder"),
            data=json.dumps({"pregunta": pregunta}),
            content_type="application/json",
        )

    def test_widget_aparece_en_catalogo(self):
        respuesta = self.client.get(reverse("index"))
        self.assertContains(respuesta, "Asistente Full Cars")
        self.assertContains(respuesta, "Ayuda local y rápida")

    def test_endpoint_requiere_post_y_pregunta(self):
        self.assertEqual(self.client.get(reverse("asistente_responder")).status_code, 405)
        self.assertEqual(self._preguntar("").status_code, 400)
        self.assertEqual(self._preguntar("x" * 201).status_code, 400)

    def test_endpoint_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        respuesta = cliente.post(
            reverse("asistente_responder"),
            data=json.dumps({"pregunta": "Hola"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_busqueda_devuelve_solo_productos_disponibles(self):
        Producto.objects.create(
            categoria=self.categoria,
            nombre_producto="Aceite oculto",
            precio=Decimal("9990"),
            stock=0,
            estado="activo",
        )
        respuesta = self._preguntar("Busco aceite")
        datos = respuesta.json()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([producto["nombre"] for producto in datos["productos"]], ["Aceite 10W40"])

    def test_pregunta_frecuente_no_requiere_api_externa(self):
        respuesta = self._preguntar("¿Cómo recupero mi contraseña?")
        self.assertIn("Olvidaste tu contraseña", respuesta.json()["respuesta"])

    def test_ayuda_describe_capacidades_sin_inventar_productos(self):
        datos = self._preguntar("Ayuda").json()
        self.assertIn("Puedo buscar repuestos", datos["respuesta"])
        self.assertNotIn("productos", datos)

    def test_respuesta_de_pedidos_cambia_si_hay_sesion(self):
        invitado = self._preguntar("¿Cómo veo mis pedidos?").json()["respuesta"]
        self.client.force_login(self.usuario)
        cliente = self._preguntar("¿Cómo veo mis pedidos?").json()["respuesta"]
        self.assertIn("Inicia sesión", invitado)
        self.assertIn("Puedes revisar", cliente)
