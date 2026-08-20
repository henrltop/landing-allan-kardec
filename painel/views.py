from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from imprensa.models import Materia

from .forms import CompromissoForm, DemandaForm, LiderancaForm, NoticiaForm
from .models import Compromisso, DemandaEscuta, Lideranca


class Entrar(LoginView):
    template_name = "painel/entrar.html"
    redirect_authenticated_user = True


class Sair(LogoutView):
    pass


@login_required
def inicio(request):
    contexto = {
        "n_liderancas": Lideranca.objects.count(),
        "n_compromissos": Compromisso.objects.exclude(status__in=["realizado", "cancelado"]).count(),
        "n_demandas_abertas": DemandaEscuta.objects.exclude(status="respondida").count(),
        "materias_pendentes": Materia.objects.filter(status="pendente"),
        "proximos": Compromisso.objects.exclude(status__in=["realizado", "cancelado"])[:5],
    }
    return render(request, "painel/inicio.html", contexto)


# ---------- Lideranças ----------
@login_required
def liderancas(request):
    q = request.GET.get("q", "").strip()
    itens = Lideranca.objects.all()
    if q:
        itens = itens.filter(Q(nome__icontains=q) | Q(municipio__icontains=q) | Q(funcao__icontains=q))
    return render(request, "painel/liderancas.html", {"itens": itens, "q": q})


# ---------- Agenda ----------
@login_required
def agenda(request):
    import calendar as pycal
    from datetime import date

    from django.utils import timezone

    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
        primeiro = date(ano, mes, 1)
    except ValueError:
        ano, mes, primeiro = hoje.year, hoje.month, date(hoje.year, hoje.month, 1)

    semanas_raw = pycal.Calendar(firstweekday=6).monthdatescalendar(ano, mes)
    eventos = Compromisso.objects.filter(
        inicio__date__gte=semanas_raw[0][0], inicio__date__lte=semanas_raw[-1][-1]
    )
    por_dia = {}
    for e in eventos:
        por_dia.setdefault(timezone.localtime(e.inicio).date(), []).append(e)

    semanas = [
        [{"dia": d, "no_mes": d.month == mes, "hoje": d == hoje, "eventos": por_dia.get(d, [])} for d in sem]
        for sem in semanas_raw
    ]
    anterior = date(ano - 1, 12, 1) if mes == 1 else date(ano, mes - 1, 1)
    proximo = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)

    contexto = {
        "semanas": semanas, "primeiro": primeiro,
        "anterior": anterior, "proximo": proximo,
        "visao": request.GET.get("visao", "calendario"),
        "itens": Compromisso.objects.all(),
    }
    return render(request, "painel/agenda.html", contexto)


# ---------- Demandas ----------
@login_required
def demandas(request):
    status = request.GET.get("status", "")
    itens = DemandaEscuta.objects.all()
    if status:
        itens = itens.filter(status=status)
    return render(request, "painel/demandas.html",
                  {"itens": itens, "status": status, "STATUS": DemandaEscuta.STATUS})


# ---------- CRUD genérico (criar / editar / excluir) ----------
MODELOS = {
    "liderancas": (Lideranca, LiderancaForm, "Liderança"),
    "agenda": (Compromisso, CompromissoForm, "Compromisso"),
    "demandas": (DemandaEscuta, DemandaForm, "Demanda da escuta"),
    "materias": (Materia, NoticiaForm, "Notícia"),
}


@login_required
def editar(request, tipo, pk=None):
    if tipo not in MODELOS:
        raise Http404
    Modelo, Form, rotulo = MODELOS[tipo]
    obj = get_object_or_404(Modelo, pk=pk) if pk else None
    inicial = {"inicio": request.GET["inicio"]} if request.GET.get("inicio") and not obj else None
    form = Form(request.POST or None, request.FILES or None, instance=obj, initial=inicial)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"painel:{tipo}")
    titulo = ("Editar" if obj else "Cadastrar") + " " + rotulo.lower()
    return render(request, "painel/form.html", {"form": form, "titulo": titulo, "voltar": tipo})


@login_required
def excluir(request, tipo, pk):
    if tipo not in MODELOS:
        raise Http404
    Modelo, _, rotulo = MODELOS[tipo]
    obj = get_object_or_404(Modelo, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect(f"painel:{tipo}")
    return render(request, "painel/excluir.html", {"obj": obj, "rotulo": rotulo, "voltar": tipo})


# ---------- Matérias da imprensa ----------
@login_required
def materias(request):
    status = request.GET.get("status", "pendente")
    itens = Materia.objects.all()
    if status:
        itens = itens.filter(status=status)
    return render(request, "painel/materias.html",
                  {"itens": itens, "status": status, "STATUS": Materia.STATUS})


@login_required
def materia(request, pk):
    obj = get_object_or_404(Materia, pk=pk)
    return render(request, "painel/materia.html", {"m": obj})


@login_required
@require_POST
def moderar(request, pk, acao):
    obj = get_object_or_404(Materia, pk=pk)
    if acao == "aprovar":
        obj.aprovar()
    elif acao == "rejeitar":
        obj.status = "rejeitada"
        obj.save(update_fields=["status"])
    return redirect("painel:materias")
