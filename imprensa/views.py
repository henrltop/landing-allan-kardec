import time

from django.shortcuts import get_object_or_404, redirect, render

from .forms import MateriaForm
from .models import Materia

INTERVALO_MIN_SEGUNDOS = 60  # limite de 1 envio por minuto por sessão


def enviar_materia(request):
    erro_ritmo = False
    if request.method == "POST":
        ultimo = request.session.get("ultimo_envio", 0)
        if time.time() - ultimo < INTERVALO_MIN_SEGUNDOS:
            erro_ritmo = True
            form = MateriaForm(request.POST, request.FILES)
        else:
            form = MateriaForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                request.session["ultimo_envio"] = time.time()
                return redirect("imprensa:enviada")
    else:
        form = MateriaForm()
    return render(request, "imprensa/enviar.html", {"form": form, "erro_ritmo": erro_ritmo})


def materia_enviada(request):
    return render(request, "imprensa/enviada.html")


def lista_noticias(request):
    noticias = Materia.objects.filter(status="aprovada")
    return render(request, "imprensa/noticias.html", {"noticias": noticias})


def detalhe_noticia(request, pk):
    noticia = get_object_or_404(Materia, pk=pk, status="aprovada")
    return render(request, "imprensa/noticia.html", {"noticia": noticia})
