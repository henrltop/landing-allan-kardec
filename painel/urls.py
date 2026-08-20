from django.urls import path

from . import views

app_name = "painel"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("entrar/", views.Entrar.as_view(), name="entrar"),
    path("sair/", views.Sair.as_view(), name="sair"),

    path("liderancas/", views.liderancas, name="liderancas"),
    path("agenda/", views.agenda, name="agenda"),
    path("demandas/", views.demandas, name="demandas"),

    path("<str:tipo>/novo/", views.editar, name="novo"),
    path("<str:tipo>/<int:pk>/editar/", views.editar, name="editar"),
    path("<str:tipo>/<int:pk>/excluir/", views.excluir, name="excluir"),

    path("materias/", views.materias, name="materias"),
    path("materias/<int:pk>/", views.materia, name="materia"),
    path("materias/<int:pk>/<str:acao>/", views.moderar, name="moderar"),
]
