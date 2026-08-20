"""
Serviço de sincronização Instagram → banco.

Fluxo: valida config → snapshot do perfil → descobre/atualiza mídias →
seleciona quais precisam de insights (estratégia por idade) → salva
snapshots → registra a execução. Erro em uma mídia não interrompe as demais.
"""
import logging
from datetime import datetime, timedelta, timezone as tz

from django.utils import timezone

from .client import MetaAPIError, MetaInstagramClient
from .metrics_config import MEDIA_FIELDS, STORY_METRICS, metrics_para_midia
from .models import (InstagramAccountDailyInsight, InstagramAccountSnapshot,
                     InstagramCollectionRun, InstagramMedia,
                     InstagramMediaMetrics, InstagramStory,
                     InstagramStoryMetrics)
from .normalize import normalizar_insights

logger = logging.getLogger("analytics.sync")

# Estratégia de frequência (idade da publicação → intervalo mínimo entre snapshots)
FAIXAS_ATUALIZACAO = [
    (timedelta(hours=48), timedelta(minutes=50)),   # até 48h: a cada execução (~1h)
    (timedelta(days=7), timedelta(hours=6)),        # 3-7 dias: a cada 6h
    (timedelta(days=30), timedelta(hours=48)),      # até 30 dias: a cada 2 dias
    (None, timedelta(days=7)),                      # mais antigas: semanal
]
INTERVALO_MINIMO_SNAPSHOT = timedelta(minutes=10)   # dedupe de segurança


def _precisa_snapshot(media, agora):
    ultimo = media.ultimo_snapshot
    if ultimo is None:
        return True
    idade_snapshot = agora - ultimo.collected_at
    if idade_snapshot < INTERVALO_MINIMO_SNAPSHOT:
        return False
    idade_publicacao = agora - media.published_at
    for limite, intervalo in FAIXAS_ATUALIZACAO:
        if limite is None or idade_publicacao <= limite:
            return idade_snapshot >= intervalo
    return False


def _parse_ts(valor):
    # Meta envia "2026-08-20T12:57:47+0000"
    return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S%z")


def sincronizar(since=None, until=None, max_midias=None, apenas_media_id=None,
                forcar_snapshot=False):
    """
    Executa uma coleta completa. Retorna o InstagramCollectionRun.
    - since/until: strings YYYY-MM-DD (opcional)
    - max_midias: teto de mídias processadas
    - apenas_media_id: sincroniza uma única mídia (modo teste)
    - forcar_snapshot: ignora a estratégia de frequência
    """
    escopo = (f"midia={apenas_media_id}" if apenas_media_id
              else f"since={since or '-'} until={until or '-'} max={max_midias or '-'}")
    run = InstagramCollectionRun.objects.create(escopo=escopo)
    erros = []
    agora = timezone.now()

    try:
        cliente = MetaInstagramClient()

        # 1-3. perfil + snapshot (pulado no modo mídia única)
        if not apenas_media_id:
            perfil = cliente.perfil()
            InstagramAccountSnapshot.objects.create(
                instagram_account_id=perfil["id"],
                username=perfil.get("username", ""),
                name=perfil.get("name", ""),
                followers_count=perfil.get("followers_count", 0),
                media_count=perfil.get("media_count", 0),
            )

            # 3b. métricas diárias retroativas da conta (janela de 30 dias)
            try:
                run.dias_atualizados = _coletar_diarios(cliente, agora)
            except Exception as exc:  # noqa: BLE001
                erros.append(f"insights diários: {exc}")
                logger.exception("Erro nos insights diários da conta")

            # 3c. stories ativas + snapshots
            try:
                run.stories_snapshots = _coletar_stories(cliente, agora, erros)
            except Exception as exc:  # noqa: BLE001
                erros.append(f"stories: {exc}")
                logger.exception("Erro na coleta de stories")

        # 4-5. descobrir novas / atualizar metadados
        midias_alvo = []
        if apenas_media_id:
            dados = cliente._get(apenas_media_id, {"fields": ",".join(MEDIA_FIELDS)})
            midias_alvo.append(_upsert_midia(dados, run))
        else:
            for dados in cliente.midias(since=since, until=until, max_itens=max_midias):
                try:
                    midias_alvo.append(_upsert_midia(dados, run))
                except Exception as exc:  # noqa: BLE001 — uma mídia não derruba a coleta
                    erros.append(f"upsert {dados.get('id')}: {exc}")
                    logger.exception("Erro ao salvar mídia %s", dados.get("id"))

        # 6-8. insights + snapshots
        for media in midias_alvo:
            if media is None:
                continue
            try:
                if not forcar_snapshot and not _precisa_snapshot(media, agora):
                    continue
                metricas = metrics_para_midia(media.media_type, media.media_product_type)
                crus, _usadas = cliente.insights(media.instagram_media_id, metricas)
                normalizado = normalizar_insights(crus)
                InstagramMediaMetrics.objects.create(
                    media=media, raw_response=crus, **normalizado)
                run.snapshots_created += 1
            except MetaAPIError as exc:
                erros.append(f"insights {media.instagram_media_id}: {exc}")
                logger.warning("Insights indisponíveis para %s: %s", media.instagram_media_id, exc)
            except Exception as exc:  # noqa: BLE001
                erros.append(f"snapshot {media.instagram_media_id}: {exc}")
                logger.exception("Erro no snapshot de %s", media.instagram_media_id)

        run.requests_made = cliente.requests_feitas
        run.errors_count = len(erros)
        run.error_summary = "\n".join(erros[:50])
        run.status = "parcial" if erros else "sucesso"

    except Exception as exc:  # noqa: BLE001 — falha geral (config, rede, token)
        logger.exception("Coleta falhou")
        run.errors_count = len(erros) + 1
        run.error_summary = ("\n".join(erros[:49]) + f"\nFATAL: {exc}").strip()
        run.status = "erro"

    run.finished_at = timezone.now()
    run.save()
    return run


def _coletar_diarios(cliente, agora):
    """Upsert das métricas diárias da conta (novos seguidores e alcance por dia)."""
    since = (agora - timedelta(days=29)).date().isoformat()
    until = agora.date().isoformat()
    atualizados = set()
    for item in cliente.insights_diarios(since, until):
        nome = item.get("name")
        for valor in item.get("values", []):
            dia = (valor.get("end_time") or "")[:10]
            if not dia:
                continue
            campo = {"follower_count": "new_followers", "reach": "reach"}.get(nome)
            if not campo:
                continue
            InstagramAccountDailyInsight.objects.update_or_create(
                date=dia, defaults={campo: valor.get("value")})
            atualizados.add(dia)
    return len(atualizados)


def _coletar_stories(cliente, agora, erros):
    """Stories ativas: upsert + snapshot de métricas (dedupe de 10 min)."""
    snapshots = 0
    for dados in cliente.stories():
        try:
            story, _ = InstagramStory.objects.update_or_create(
                instagram_media_id=dados["id"],
                defaults={
                    "media_type": dados.get("media_type") or "",
                    "permalink": dados.get("permalink") or "",
                    "published_at": _parse_ts(dados["timestamp"]),
                })
            ultimo = story.ultimo_snapshot
            if ultimo and agora - ultimo.collected_at < INTERVALO_MINIMO_SNAPSHOT:
                continue
            crus, _usadas = cliente.insights(dados["id"], STORY_METRICS)
            valores = {}
            for item in crus:
                if item.get("values") and item["name"] in (
                        "views", "reach", "replies", "shares",
                        "total_interactions", "navigation"):
                    valores[item["name"]] = item["values"][0].get("value")
            InstagramStoryMetrics.objects.create(story=story, raw_response=crus, **valores)
            snapshots += 1
        except MetaAPIError as exc:
            erros.append(f"story {dados.get('id')}: {exc}")
            logger.warning("Story %s sem insights: %s", dados.get("id"), exc)
    return snapshots


def _upsert_midia(dados, run):
    """Cria ou atualiza os metadados de uma mídia. Snapshots ficam intactos."""
    obj, criada = InstagramMedia.objects.update_or_create(
        instagram_media_id=dados["id"],
        defaults={
            "caption": dados.get("caption") or "",
            "media_type": dados.get("media_type") or "",
            "media_product_type": dados.get("media_product_type") or "",
            "permalink": dados.get("permalink") or "",
            "thumbnail_url": dados.get("thumbnail_url") or dados.get("media_url") or "",
            "like_count": dados.get("like_count"),
            "comments_count": dados.get("comments_count"),
            "published_at": _parse_ts(dados["timestamp"]),
        },
    )
    if criada:
        run.media_discovered += 1
    else:
        run.media_updated += 1
    return obj
