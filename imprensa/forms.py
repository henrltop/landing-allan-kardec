from django import forms

from .models import Materia

MAX_IMAGEM_MB = 5


class MateriaForm(forms.ModelForm):
    # Honeypot: campo invisível — humanos deixam vazio, robôs de spam preenchem
    site = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Materia
        fields = ["jornalista", "veiculo", "email", "telefone", "titulo", "texto", "link", "imagem"]

    def clean_site(self):
        if self.cleaned_data.get("site"):
            raise forms.ValidationError("Envio inválido.")
        return ""

    def clean_imagem(self):
        imagem = self.cleaned_data.get("imagem")
        if imagem and imagem.size > MAX_IMAGEM_MB * 1024 * 1024:
            raise forms.ValidationError(f"A imagem deve ter no máximo {MAX_IMAGEM_MB} MB.")
        return imagem
