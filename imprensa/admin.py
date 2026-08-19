from django.contrib import admin

from .models import Materia


@admin.action(description="Aprovar e publicar matérias selecionadas")
def aprovar_materias(modeladmin, request, queryset):
    for materia in queryset:
        materia.aprovar()


@admin.action(description="Rejeitar matérias selecionadas")
def rejeitar_materias(modeladmin, request, queryset):
    queryset.update(status="rejeitada")


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "titulo", "veiculo", "jornalista", "status", "publicado_em")
    list_filter = ("status", "veiculo")
    search_fields = ("titulo", "texto", "jornalista", "veiculo", "email")
    date_hierarchy = "criado_em"
    actions = [aprovar_materias, rejeitar_materias]
    readonly_fields = ("criado_em", "publicado_em")
