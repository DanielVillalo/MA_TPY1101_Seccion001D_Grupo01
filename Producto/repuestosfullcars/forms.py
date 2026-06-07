from django import forms

from .models import Producto


class CheckoutForm(forms.Form):
    direccion_envio = forms.CharField(
        label="Direccion de envio",
        min_length=8,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
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

    def clean_estado(self):
        estado = self.cleaned_data["estado"]
        if estado not in {"activo", "inactivo"}:
            raise forms.ValidationError("Selecciona un estado valido.")
        return estado
