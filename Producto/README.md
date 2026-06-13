# Repuestos Full Cars

Proyecto académico desarrollado con Django. Incluye catálogo, búsqueda, usuarios,
carrito, pedidos, administración de inventario, asistente y pago opcional con
Mercado Pago.

## Ejecución local en Windows

Desde PowerShell, dentro de la carpeta `Producto`:

```powershell
& "$env:LOCALAPPDATA\Python\bin\python.exe" -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
& .\.venv\Scripts\python.exe manage.py migrate
& .\.venv\Scripts\python.exe manage.py seed_categories
& .\.venv\Scripts\python.exe manage.py createsuperuser
& .\.venv\Scripts\python.exe manage.py runserver
```

Abrir `http://127.0.0.1:8000/`.

Estos comandos no requieren activar el entorno virtual.

## Modo local y Mercado Pago

Las claves de Mercado Pago son opcionales para las pruebas locales. Si
`MP_ACCESS_TOKEN` y `MP_PUBLIC_KEY` están vacías, el pedido se registra en modo
local y se puede revisar desde "Mis pedidos" y desde la administración.

Para probar el pago de Mercado Pago se deben agregar las credenciales de prueba
en `.env`. El archivo `.env` está ignorado por Git y no se debe publicar.

## Pruebas antes de publicar

```powershell
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py makemigrations --check
& .\.venv\Scripts\python.exe manage.py test
```

Después se recomienda probar manualmente:

1. Buscar y filtrar productos.
2. Registrarse e iniciar sesión.
3. Agregar productos al carrito y cambiar cantidades.
4. Confirmar un pedido y revisar el descuento de stock.
5. Ingresar como administrador y entregar o anular el pedido.
6. Revisar la página en vista móvil desde las herramientas de Chrome.

Los cambios se pueden revisar con `git status` y `git diff`. Un commit permanece
local hasta ejecutar `git push`.
