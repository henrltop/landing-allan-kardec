from django.contrib import admin

from .models import Compromisso, DemandaEscuta, Lideranca


@admin.register(Lideranca)
class LiderancaAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "funcao", "telefone", "atualizado_em")
    list_filter = ("municipio",)
    search_fields = ("nome", "municipio", "funcao", "telefone", "email")


@admin.register(Compromisso)
class CompromissoAdmin(admin.ModelAdmin):
    list_display = ("inicio", "titulo", "municipio", "local", "responsavel", "status")
    list_filter = ("status", "municipio")
    search_fields = ("titulo", "municipio", "local", "responsavel")
    date_hierarchy = "inicio"


@admin.register(DemandaEscuta)
class DemandaEscutaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "tema", "municipio", "origem", "status")
    list_filter = ("status", "tema", "origem", "municipio")
    search_fields = ("municipio", "descricao", "nome_contato", "contato")
    date_hierarchy = "criado_em"
