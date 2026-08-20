import csv
import json

import markdown as md
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .evolucao import curva, marcos_da_midia, resumo_crescimento
from .models import (InstagramAccountDailyInsight, InstagramAccountSnapshot,
                     InstagramCollectionRun, InstagramMedia, InstagramStory,
                     RelatorioAnalise)
from .normalize import metricas_derivadas


def _render_markdown(texto):
    return md.markdown(texto, extensions=["tables", "sane_lists", "nl2br"])

ORDENACOES = {
    "views": "-views", "reach": "-reach", "total_interactions": "-total_interactions",
    "shares": "-shares", "reposts": "-reposts", "comments": "-comments",
    "skip_rate": "reels_skip_rate", "watch_time": "-avg_watch_time_ms",
}


def _midias_filtradas(request):
    """Aplica os filtros comuns (período, tipo) à lista de mídias."""
    qs = InstagramMedia.objects.all()
    inicio = parse_date(request.GET.get("inicio") or "")
    fim = parse_date(request.GET.get("fim") or "")
    tipo = request.GET.get("tipo", "")
    if inicio:
        qs = qs.filter(published_at__date__gte=inicio)
    if fim:
        qs = qs.filter(published_at__date__lte=fim)
    if tipo in ("REELS", "FEED"):
        qs = qs.filter(media_product_type=tipo)
    elif tipo in ("IMAGE", "VIDEO", "CAROUSEL_ALBUM"):
        qs = qs.filter(media_type=tipo)
    return qs


def _com_ultimo_snapshot(midias):
    """Anexa o último snapshot a cada mídia (1 consulta por página é aceitável aqui)."""
    resultado = []
    for m in midias:
        m.snap = m.ultimo_snapshot
        resultado.append(m)
    return resultado


# ---------------- Dashboard (painel, login) ----------------

@login_required
def dashboard(request):
    contexto = {"secao_ativa": "instagram"}

    # Perfil: atual, ontem, semana
    snaps_perfil = list(InstagramAccountSnapshot.objects.order_by("-collected_at")[:400])
    atual = snaps_perfil[0] if snaps_perfil else None
    contexto["perfil"] = atual
    if atual:
        agora = timezone.now()

        def perfil_em(dias):
            alvo = agora - timezone.timedelta(days=dias)
            candidatos = [s for s in snaps_perfil if s.collected_at <= alvo]
            return candidatos[0] if candidatos else snaps_perfil[-1]

        ontem, semana = perfil_em(1), perfil_em(7)
        contexto["cresc_dia"] = atual.followers_count - ontem.followers_count
        contexto["cresc_semana"] = atual.followers_count - semana.followers_count
        contexto["serie_seguidores"] = list(reversed(snaps_perfil))[-60:]

    # Totais do período filtrado (último snapshot de cada mídia)
    midias = _com_ultimo_snapshot(_midias_filtradas(request))
    def soma(campo):
        return sum(getattr(m.snap, campo, None) or 0 for m in midias if m.snap)
    contexto["totais"] = {
        "conteudos": len(midias), "views": soma("views"), "reach": soma("reach"),
        "interacoes": soma("total_interactions"), "shares": soma("shares"),
        "reposts": soma("reposts"), "comments": soma("comments"),
    }

    # Ranking
    ordem = request.GET.get("ordem", "views")
    campo = {"views": "views", "reach": "reach", "total_interactions": "total_interactions",
             "shares": "shares", "reposts": "reposts", "comments": "comments",
             "skip_rate": "reels_skip_rate", "watch_time": "avg_watch_time_ms"}.get(ordem, "views")
    com_metricas = [m for m in midias if m.snap and getattr(m.snap, campo, None) is not None]
    reverso = ordem != "skip_rate"  # menor skip rate é melhor
    com_metricas.sort(key=lambda m: getattr(m.snap, campo) or 0, reverse=reverso)
    contexto["ranking"] = com_metricas[:30]
    contexto["ordem"] = ordem
    contexto["ordenacoes"] = [
        ("views", "Views"), ("reach", "Alcance"), ("total_interactions", "Interações"),
        ("shares", "Shares"), ("reposts", "Reposts"), ("comments", "Comentários"),
        ("skip_rate", "Menor skip rate"), ("watch_time", "Maior watch time"),
    ]
    contexto["filtros"] = {"inicio": request.GET.get("inicio", ""),
                           "fim": request.GET.get("fim", ""),
                           "tipo": request.GET.get("tipo", "")}
    contexto["ultima_execucao"] = InstagramCollectionRun.objects.first()
    return render(request, "analytics/instagram.html", contexto)


@login_required
def detalhe_midia(request, pk):
    media = get_object_or_404(InstagramMedia, pk=pk)
    snap = media.ultimo_snapshot
    serie = curva(media)
    marcos = marcos_da_midia(media)
    # pontos para o gráfico SVG (views ao longo do tempo)
    grafico = [(p["horas_desde_publicacao"], p["views"]) for p in serie if p.get("views") is not None]
    svg = _grafico_svg(grafico)
    return render(request, "analytics/instagram_midia.html", {
        "m": media, "snap": snap,
        "derivadas": metricas_derivadas(snap) if snap else {},
        "serie": serie, "marcos": marcos,
        "crescimento": resumo_crescimento(media),
        "svg": svg,
    })


def _grafico_svg(pontos, largura=760, altura=230, margem=42):
    """Gera um line chart SVG simples (views x horas) sem bibliotecas."""
    if len(pontos) < 2:
        return None
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    x0, x1 = min(xs), max(xs)
    y0, y1 = 0, max(ys) or 1
    if x1 == x0:
        x1 = x0 + 1

    def px(x):
        return margem + (x - x0) / (x1 - x0) * (largura - 2 * margem)

    def py(y):
        return altura - margem - (y - y0) / (y1 - y0) * (altura - 2 * margem)

    linha = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in pontos)
    circulos = "".join(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.5" fill="#070FB5"/>'
                       for x, y in pontos)
    grade = "".join(
        f'<line x1="{margem}" y1="{py(y1 * f):.1f}" x2="{largura - margem}" y2="{py(y1 * f):.1f}" '
        f'stroke="#E2E5F5" stroke-width="1"/>'
        f'<text x="{margem - 6}" y="{py(y1 * f):.1f}" text-anchor="end" dominant-baseline="middle" '
        f'font-size="10" fill="#070FB5">{int(y1 * f):,}</text>'.replace(",", ".")
        for f in (0, .25, .5, .75, 1))
    rotulos_x = "".join(
        f'<text x="{px(x):.1f}" y="{altura - margem + 16}" text-anchor="middle" font-size="10" '
        f'fill="#070FB5">{x:.0f}h</text>'
        for x in {xs[0], xs[len(xs) // 2], xs[-1]})
    return (
        f'<svg viewBox="0 0 {largura} {altura}" role="img" aria-label="Evolução de views">'
        f'{grade}<polyline points="{linha}" fill="none" stroke="#51BC24" stroke-width="2.5"/>'
        f'{circulos}{rotulos_x}</svg>'
    )


@login_required
def sincronizar_agora(request):
    """Coleta manual imediata, disparada pelo botão do dashboard."""
    from datetime import date, timedelta as td

    from django.views.decorators.http import require_POST  # noqa: F401 (documentação)

    if request.method != "POST":
        return redirect("analytics:instagram")

    # trava anti-duplo-clique: se uma coleta começou há menos de 3 minutos, não repete
    ultima = InstagramCollectionRun.objects.first()
    if ultima and (timezone.now() - ultima.started_at).total_seconds() < 180:
        messages.warning(request, "Já houve uma coleta há menos de 3 minutos — aguarde um pouco.")
        return redirect("analytics:instagram")

    from .sync import sincronizar
    run = sincronizar(since=(date.today() - td(days=14)).isoformat(), forcar_snapshot=True)
    if run.status == "erro":
        messages.error(request, f"A coleta falhou: {run.error_summary[:300]}")
    else:
        messages.success(
            request,
            f"Dados atualizados: {run.snapshots_created} snapshots de publicações, "
            f"{run.stories_snapshots} de stories, {run.dias_atualizados} dias da conta, "
            f"{run.media_discovered} publicações novas ({run.requests_made} requisições"
            f"{', ' + str(run.errors_count) + ' erros' if run.errors_count else ''}).")
    return redirect("analytics:instagram")


# ---------------- Relatórios de análise ----------------

class RelatorioForm(forms.ModelForm):
    class Meta:
        model = RelatorioAnalise
        fields = ["titulo", "periodo_inicio", "periodo_fim", "dados_coletados_em",
                  "corpo_markdown"]
        widgets = {
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"type": "date"}),
            "dados_coletados_em": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "corpo_markdown": forms.Textarea(attrs={
                "rows": 22, "placeholder": "Cole aqui o relatório em Markdown gerado pelo Claude"}),
        }


@login_required
def relatorios(request):
    return render(request, "analytics/relatorios.html",
                  {"itens": RelatorioAnalise.objects.all()})


@login_required
def relatorio_editar(request, pk=None):
    obj = get_object_or_404(RelatorioAnalise, pk=pk) if pk else None
    form = RelatorioForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        relatorio = form.save(commit=False)
        if not relatorio.pk:
            relatorio.autor = request.user
        relatorio.save()
        return redirect("analytics:relatorio", relatorio.pk)
    return render(request, "analytics/relatorio_form.html",
                  {"form": form, "obj": obj})


@login_required
def relatorio_detalhe(request, pk):
    obj = get_object_or_404(RelatorioAnalise, pk=pk)
    return render(request, "analytics/relatorio.html",
                  {"r": obj, "html": _render_markdown(obj.corpo_markdown)})


def _ajustar_tabelas_pdf(html):
    """
    Dá larguras proporcionais ao conteúdo para as colunas das tabelas
    (o xhtml2pdf não faz auto-layout decente) e repete o cabeçalho
    quando a tabela quebra de página.
    """
    import re

    def texto_limpo(celula):
        return re.sub(r"<[^>]+>", "", celula).strip()

    def processar(m):
        tabela = m.group(0)
        linhas = re.findall(r"<tr>.*?</tr>", tabela, flags=re.S)
        if not linhas:
            return tabela
        colunas = []
        for linha in linhas:
            celulas = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", linha, flags=re.S)
            for i, cel in enumerate(celulas):
                tam = len(texto_limpo(cel))
                if i >= len(colunas):
                    colunas.append(tam)
                else:
                    colunas[i] = max(colunas[i], tam)
        if not colunas:
            return tabela
        # peso = comprimento máximo da coluna (limitado), mínimo garantido
        pesos = [min(max(c, 7), 38) for c in colunas]
        total = sum(pesos)
        larguras = [max(round(p / total * 100), 6) for p in pesos]

        # injeta width nos <th> (linha de cabeçalho define o grid da tabela)
        contador = {"i": 0}

        def poe_largura(mth):
            i = contador["i"]
            contador["i"] += 1
            largura = larguras[i] if i < len(larguras) else 10
            return mth.group(0).replace("<th", f'<th width="{largura}%"', 1)

        tabela = re.sub(r"<th(?=[\s>])[^>]*>", poe_largura, tabela, count=len(larguras))
        tabela = tabela.replace("<table>", '<table repeat="1">', 1)
        return tabela

    return re.sub(r"<table>.*?</table>", processar, html, flags=re.S)


def _pdf_via_navegador(html, rodape_texto):
    """
    Gera o PDF com motor de navegador (Chromium/Edge via Playwright):
    tipografia da marca, emojis coloridos e layout de tabela correto.
    """
    from playwright.sync_api import sync_playwright

    rodape = (
        '<div style="font-size:7.5px; width:100%; text-align:center; color:#4A4D7A; '
        'font-family:Arial, sans-serif;">'
        f'{rodape_texto} · página <span class="pageNumber"></span> de '
        '<span class="totalPages"></span></div>'
    )
    with sync_playwright() as p:
        try:
            navegador = p.chromium.launch(channel="msedge", headless=True)
        except Exception:  # noqa: BLE001 — sem Edge (ex.: VM), usa Chromium do Playwright
            navegador = p.chromium.launch(headless=True)
        try:
            pagina = navegador.new_page()
            pagina.set_content(html, wait_until="networkidle")
            return pagina.pdf(
                format="A4", print_background=True,
                display_header_footer=True,
                header_template='<div></div>', footer_template=rodape,
                margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"},
            )
        finally:
            navegador.close()


def _pdf_via_xhtml2pdf(html):
    """Fallback sem navegador (sem emojis; tabelas com larguras calculadas)."""
    import io

    from xhtml2pdf import pisa

    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(html, dest=buffer, encoding="utf-8")
    if resultado.err:
        return None
    return buffer.getvalue()


@login_required
def relatorio_pdf(request, pk):
    """Baixa o relatório como PDF (cabeçalho com a janela de dados carimbada)."""
    import logging

    from django.template.loader import render_to_string
    from django.utils.text import slugify

    obj = get_object_or_404(RelatorioAnalise, pk=pk)
    rodape_texto = (f"Professor Allan Kardec · 20020 — relatório interno · "
                    f"gerado em {timezone.localtime():%d/%m/%Y %H:%M}")
    contexto = {"r": obj, "html": _render_markdown(obj.corpo_markdown),
                "agora": timezone.localtime()}
    html = render_to_string("analytics/relatorio_pdf.html", contexto)

    try:
        pdf = _pdf_via_navegador(html, rodape_texto)
    except Exception:  # noqa: BLE001
        logging.getLogger("analytics").exception("PDF via navegador falhou; usando fallback")
        contexto["html"] = _ajustar_tabelas_pdf(contexto["html"])
        html = render_to_string("analytics/relatorio_pdf.html", contexto)
        pdf = _pdf_via_xhtml2pdf(html)

    if not pdf:
        return HttpResponse("Falha ao gerar o PDF deste relatório.", status=500)
    resposta = HttpResponse(pdf, content_type="application/pdf")
    nome = slugify(obj.titulo)[:60] or "relatorio"
    resposta["Content-Disposition"] = (
        f'attachment; filename="relatorio_{nome}_{obj.periodo_inicio:%Y-%m-%d}.pdf"')
    return resposta


@login_required
def relatorio_excluir(request, pk):
    obj = get_object_or_404(RelatorioAnalise, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("analytics:relatorios")
    return render(request, "painel/excluir.html",
                  {"obj": obj, "rotulo": "Relatório", "voltar_url": "analytics:relatorios"})


# ---------------- Destaques públicos (carrossel da landing) ----------------

def destaques_instagram(request):
    """
    Últimos posts para o carrossel público da landing.
    Expõe SOMENTE conteúdo já público no Instagram (thumbnail, legenda,
    link, data) — nunca métricas nem dados internos.
    """
    posts = (InstagramMedia.objects.exclude(thumbnail_url="")
             .order_by("-published_at")[:10])
    return JsonResponse({"posts": [{
        "permalink": m.permalink,
        "thumbnail": m.thumbnail_url,
        "legenda": (m.caption or "")[:120],
        "data": timezone.localtime(m.published_at).strftime("%d/%m"),
        "tipo": m.media_product_type or m.media_type,
    } for m in posts]})


# ---------------- API para IA (login de sessão) ----------------

def _registro_api(m, snap=None):
    snap = snap or m.ultimo_snapshot
    if not snap:
        return None
    derivadas = metricas_derivadas(snap)
    return {
        "media_id": m.instagram_media_id,
        "published_at": m.published_at.isoformat(),
        "caption": m.caption,
        "media_type": m.media_type,
        "media_product_type": m.media_product_type,
        "views": snap.views, "reach": snap.reach, "likes": snap.likes,
        "comments": snap.comments, "saved": snap.saved, "shares": snap.shares,
        "reposts": snap.reposts, "total_interactions": snap.total_interactions,
        "avg_watch_time_seconds": derivadas["avg_watch_time_seconds"],
        "total_watch_time_seconds": derivadas["total_watch_time_seconds"],
        "skip_rate_3s": derivadas["skip_rate_3s"],
        "engagement_by_reach": derivadas["engagement_by_reach"],
        "like_rate": derivadas["like_rate"],
        "comment_rate": derivadas["comment_rate"],
        "share_rate": derivadas["share_rate"],
        "save_rate": derivadas["save_rate"],
        "repost_rate": derivadas["repost_rate"],
        "views_per_reached_account": derivadas["views_per_reached_account"],
        "snapshot_collected_at": snap.collected_at.isoformat(),
        "permalink": m.permalink,
        # campos reservados para classificação futura por IA
        "tema": m.tema or None, "subtema": m.subtema or None,
        "cidade": m.cidade or None, "resumo": m.resumo or None,
    }


@login_required
def api_media(request):
    registros = [r for r in (_registro_api(m) for m in _midias_filtradas(request))
                 if r is not None]
    return JsonResponse({"count": len(registros), "results": registros})


def _janela_export(request):
    """Lê modo (atual/periodo) e a janela datetime do formulário de exportação."""
    from django.utils.dateparse import parse_datetime

    modo = request.GET.get("modo", "atual")

    def dt(nome):
        bruto = request.GET.get(nome) or ""
        valor = parse_datetime(bruto)
        if valor and timezone.is_naive(valor):
            valor = timezone.make_aware(valor)
        return valor

    return modo, dt("periodo_inicio"), dt("periodo_fim")


def _snapshot_as_of(obj, fim):
    """Último snapshot até o instante `fim` (estado das métricas naquele momento)."""
    qs = obj.metrics.order_by("-collected_at")
    if fim:
        qs = qs.filter(collected_at__lte=fim)
    return qs.first()


def _dataset_midias(request, modo, inicio, fim):
    qs = _midias_filtradas(request)  # mantém filtro de tipo (REELS/FEED/…)
    if modo == "periodo":
        if inicio:
            qs = qs.filter(published_at__gte=inicio)
        if fim:
            qs = qs.filter(published_at__lte=fim)
    registros = []
    for m in qs:
        snap = _snapshot_as_of(m, fim) if modo == "periodo" else m.ultimo_snapshot
        registro = _registro_api(m, snap)
        if registro:
            registros.append(registro)
    return registros


def _dataset_stories(request, modo, inicio, fim):
    qs = InstagramStory.objects.all()
    if modo == "periodo":
        if inicio:
            qs = qs.filter(published_at__gte=inicio)
        if fim:
            qs = qs.filter(published_at__lte=fim)
    registros = []
    for s in qs:
        snap = _snapshot_as_of(s, fim) if modo == "periodo" else s.ultimo_snapshot
        if not snap:
            continue
        registros.append({
            "story_id": s.instagram_media_id,
            "published_at": s.published_at.isoformat(),
            "media_type": s.media_type,
            "views": snap.views, "reach": snap.reach, "replies": snap.replies,
            "shares": snap.shares, "total_interactions": snap.total_interactions,
            "navigation": snap.navigation,
            "snapshot_collected_at": snap.collected_at.isoformat(),
            "permalink": s.permalink,
        })
    return registros


def _dataset_diario(modo, inicio, fim):
    qs = InstagramAccountDailyInsight.objects.order_by("date")
    if modo == "periodo":
        if inicio:
            qs = qs.filter(date__gte=inicio.date())
        if fim:
            qs = qs.filter(date__lte=fim.date())
    return [{"date": d.date.isoformat(), "new_followers": d.new_followers,
             "reach": d.reach, "atualizado_em": d.collected_at.isoformat()} for d in qs]


def _dataset_perfil(modo, inicio, fim):
    qs = InstagramAccountSnapshot.objects.order_by("collected_at")
    if modo == "periodo":
        if inicio:
            qs = qs.filter(collected_at__gte=inicio)
        if fim:
            qs = qs.filter(collected_at__lte=fim)
    return [{"collected_at": s.collected_at.isoformat(), "username": s.username,
             "followers_count": s.followers_count, "media_count": s.media_count} for s in qs]


@login_required
def api_export(request):
    formato = request.GET.get("formato", "csv").lower()
    dataset = request.GET.get("dataset", "midias")
    modo, inicio, fim = _janela_export(request)

    if dataset == "tudo":
        # Pacote único para análise por IA: seções nomeadas + metadados da janela.
        pacote = {
            "descricao": "Export completo do Instagram @profallankardec para análise",
            "gerado_em": timezone.now().isoformat(),
            "modo": modo,
            "periodo": {"inicio": inicio.isoformat() if inicio else None,
                        "fim": fim.isoformat() if fim else None},
            "publicacoes": _dataset_midias(request, modo, inicio, fim),
            "stories": _dataset_stories(request, modo, inicio, fim),
            "conta_por_dia": _dataset_diario(modo, inicio, fim),
            "historico_seguidores": _dataset_perfil(modo, inicio, fim),
        }
        resposta = HttpResponse(json.dumps(pacote, ensure_ascii=False, indent=2),
                                content_type="application/json; charset=utf-8")
        resposta["Content-Disposition"] = f'attachment; filename="instagram_completo_{modo}.json"'
        return resposta

    if dataset == "stories":
        registros = _dataset_stories(request, modo, inicio, fim)
    elif dataset == "diario":
        registros = _dataset_diario(modo, inicio, fim)
    elif dataset == "perfil":
        registros = _dataset_perfil(modo, inicio, fim)
    else:
        dataset = "midias"
        registros = _dataset_midias(request, modo, inicio, fim)

    sufixo = f"{dataset}_{modo}"
    if formato == "csv":
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = f'attachment; filename="instagram_{sufixo}.csv"'
        if registros:
            escritor = csv.DictWriter(resposta, fieldnames=list(registros[0].keys()))
            escritor.writeheader()
            escritor.writerows(registros)
        return resposta
    resposta = HttpResponse(json.dumps(registros, ensure_ascii=False, indent=2),
                            content_type="application/json; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="instagram_{sufixo}.json"'
    return resposta
