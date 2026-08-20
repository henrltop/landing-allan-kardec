from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("painel/instagram/", views.dashboard, name="instagram"),
    path("painel/instagram/sincronizar/", views.sincronizar_agora, name="sincronizar"),
    path("painel/instagram/<int:pk>/", views.detalhe_midia, name="midia"),
    path("painel/relatorios/", views.relatorios, name="relatorios"),
    path("painel/relatorios/novo/", views.relatorio_editar, name="relatorio_novo"),
    path("painel/relatorios/<int:pk>/", views.relatorio_detalhe, name="relatorio"),
    path("painel/relatorios/<int:pk>/pdf/", views.relatorio_pdf, name="relatorio_pdf"),
    path("painel/relatorios/<int:pk>/editar/", views.relatorio_editar, name="relatorio_editar"),
    path("painel/relatorios/<int:pk>/excluir/", views.relatorio_excluir, name="relatorio_excluir"),
    path("api/instagram/destaques", views.destaques_instagram, name="destaques"),
    path("api/analytics/instagram/media", views.api_media, name="api_media"),
    path("api/analytics/instagram/export", views.api_export, name="api_export"),
]
