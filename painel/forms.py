from django import forms

from imprensa.models import Materia

from .models import Compromisso, DemandaEscuta, Lideranca


class NoticiaForm(forms.ModelForm):
    """Cadastro de notícia pela equipe: produção própria ou registro de 'saiu na mídia'."""

    class Meta:
        model = Materia
        fields = ["tipo", "titulo", "veiculo", "jornalista", "texto", "link", "imagem", "status"]
        labels = {
            "veiculo": "Veículo / fonte (ex.: Equipe 20020, Gazeta MT…)",
            "link": "Link da publicação original (para 'saiu na mídia')",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["tipo"].initial = "equipe"
            self.fields["status"].initial = "aprovada"


class LiderancaForm(forms.ModelForm):
    class Meta:
        model = Lideranca
        fields = ["nome", "municipio", "funcao", "telefone", "email", "observacoes"]


class CompromissoForm(forms.ModelForm):
    class Meta:
        model = Compromisso
        fields = ["titulo", "inicio", "municipio", "local", "descricao", "responsavel", "status"]
        widgets = {"inicio": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class DemandaForm(forms.ModelForm):
    class Meta:
        model = DemandaEscuta
        fields = ["tema", "municipio", "descricao", "origem", "nome_contato", "contato", "status", "resposta"]
