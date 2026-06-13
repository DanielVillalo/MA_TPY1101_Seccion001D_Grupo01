from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .models import Producto


class RegistroForm(forms.Form):
    username = forms.CharField(min_length=3, max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirmPassword = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya existe.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este correo ya está asociado a una cuenta.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirmacion = cleaned_data.get("confirmPassword")
        if password and confirmacion and password != confirmacion:
            self.add_error("confirmPassword", "Las contraseñas no coinciden.")
        if password:
            usuario = User(
                username=cleaned_data.get("username", ""),
                email=cleaned_data.get("email", ""),
            )
            try:
                password_validation.validate_password(password, usuario)
            except ValidationError as errores:
                self.add_error("password", errores)
        return cleaned_data

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
        )


class CheckoutForm(forms.Form):
    nombre_receptor = forms.CharField(
        label="Nombre de quien recibe",
        min_length=3,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej: Cristina Hernández",
                "autocomplete": "name",
            }
        ),
    )
    telefono_contacto = forms.CharField(
        label="Teléfono de contacto",
        max_length=25,
        validators=[
            RegexValidator(
                regex=r"^\+?[\d\s-]{8,20}$",
                message="Ingresa un teléfono válido de al menos 8 dígitos.",
            )
        ],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej: +56 9 1234 5678",
                "autocomplete": "tel",
                "inputmode": "tel",
            }
        ),
    )
    comuna = forms.CharField(
        label="Comuna",
        min_length=2,
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ej: Santiago"}
        ),
    )
    ciudad = forms.CharField(
        label="Ciudad",
        min_length=2,
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ej: Santiago"}
        ),
    )
    direccion_envio = forms.CharField(
        label="Dirección de envío",
        min_length=8,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Calle, número, departamento o casa",
                "autocomplete": "street-address",
            }
        ),
    )
    referencia_entrega = forms.CharField(
        label="Referencia para la entrega",
        required=False,
        max_length=250,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Ej: Portón gris, dejar en conserjería (opcional)",
            }
        ),
    )


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            "nombre_producto",
            "categoria",
            "descripcion",
            "precio",
            "stock",
            "estado",
            "imagen_url",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            clase = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs["class"] = clase
            if nombre in {"precio", "stock"}:
                campo.widget.attrs["min"] = "0"
            if nombre == "precio":
                campo.widget.attrs["step"] = "1"
            if nombre == "descripcion":
                campo.widget.attrs["rows"] = "3"

    def clean_estado(self):
        estado = self.cleaned_data["estado"]
        if estado not in {"activo", "inactivo"}:
            raise forms.ValidationError("Selecciona un estado valido.")
        return estado
