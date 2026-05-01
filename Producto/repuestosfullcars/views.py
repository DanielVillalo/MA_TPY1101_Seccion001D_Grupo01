from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from .models import Producto, Categoria

# --- VISTAS PÚBLICAS ---

def index(request):
    productos = Producto.objects.all()
    return render(request, 'repuestosfullcars/home.html', {'productos': productos})

def registro(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        e = request.POST.get('email')
        p = request.POST.get('password')
        c = request.POST.get('confirmPassword')

        if p != c:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, 'usuarios/registro.html')
        
        if User.objects.filter(username=u).exists():
            messages.error(request, "Este nombre de usuario ya existe.")
            return render(request, 'usuarios/registro.html')

        try:
            # create_user asegura que el usuario sea 'cliente' por defecto (is_staff=0)
            nuevo_usuario = User.objects.create_user(username=u, email=e, password=p)
            nuevo_usuario.save()
            messages.success(request, f"¡Bienvenido {u}! Ya puedes iniciar sesión.")
            return redirect('login')
        except Exception as err:
            messages.error(request, f"Error al crear cuenta: {err}")
            return render(request, 'usuarios/registro.html')

    return render(request, 'usuarios/registro.html')


# --- VISTAS DE ADMINISTRACIÓN (CRUD) ---

@staff_member_required # Solo usuarios con "Staff Status" (el check verde) pueden entrar
def admin_productos(request):
    producto_edit = None
    categorias = Categoria.objects.all()
    
    # Si recibimos un ID por la URL (p.ej. ?edit=5), buscamos el producto para editarlo
    edit_id = request.GET.get('edit')
    if edit_id:
        producto_edit = get_object_or_404(Producto, id=edit_id)

    if request.method == 'POST':
        p_id = request.POST.get('producto_id')
        
        # Captura de datos del formulario (Nombres de tus modelos)
        nombre = request.POST.get('nombre_producto')
        desc = request.POST.get('descripcion')
        precio = request.POST.get('precio')
        stock = request.POST.get('stock')
        categoria_id = request.POST.get('categoria')
        estado = request.POST.get('estado')
        imagen = request.FILES.get('imagen_url')

        try:
            cat_obj = Categoria.objects.get(id=categoria_id)
            
            if p_id: # ACCIÓN: ACTUALIZAR
                p = get_object_or_404(Producto, id=p_id)
                p.nombre_producto = nombre
                p.descripcion = desc
                p.precio = precio
                p.stock = stock
                p.categoria = cat_obj
                p.estado = estado
                if imagen: 
                    p.imagen_url = imagen
                p.save()
                messages.success(request, f"Producto '{nombre}' actualizado correctamente.")
            else: # ACCIÓN: CREAR
                Producto.objects.create(
                    nombre_producto=nombre, 
                    descripcion=desc, 
                    precio=precio,
                    stock=stock, 
                    categoria=cat_obj, 
                    estado=estado, 
                    imagen_url=imagen
                )
                messages.success(request, f"Producto '{nombre}' agregado al inventario.")
            
            return redirect('admin_productos')
            
        except Exception as e:
            messages.error(request, f"Hubo un error al procesar el producto: {e}")

    # Listamos los productos, los más nuevos primero
    productos = Producto.objects.all().order_by('-fecha_actualizacion')
    
    return render(request, 'repuestosfullcars/admin_productos.html', {
        'productos': productos,
        'categorias': categorias,
        'producto_edit': producto_edit
    })

@staff_member_required
def eliminar_producto(request, id):
    p = get_object_or_404(Producto, id=id)
    nombre = p.nombre_producto
    p.delete()
    messages.warning(request, f"El producto '{nombre}' ha sido eliminado.")
    return redirect('admin_productos')