from django.urls import path

from . import views

app_name = "imprensa"

urlpatterns = [
    path("imprensa/", views.enviar_materia, name="enviar"),
    path("imprensa/enviada/", views.materia_enviada, name="enviada"),
    path("noticias/", views.lista_noticias, name="noticias"),
    path("noticias/<int:pk>/", views.detalhe_noticia, name="noticia"),
]
