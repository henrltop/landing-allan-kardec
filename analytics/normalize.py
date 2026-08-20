"""
Normalização dos Insights da Meta e cálculo de métricas derivadas.

A Meta retorna [{"name": "views", "period": "lifetime", "values": [{"value": N}]}].
Aqui isso vira um dicionário plano; o JSON cru é preservado à parte para auditoria.
"""
from .metrics_config import NORMALIZED_NAMES


def normalizar_insights(lista_crua):
    """Converte a lista crua da Meta em {campo_normalizado: valor}."""
    normalizado = {}
    for item in lista_crua or []:
        nome = NORMALIZED_NAMES.get(item.get("name"))
        if not nome:
            continue  # métrica desconhecida fica só no raw_response
        valores = item.get("values") or []
        if not valores:
            continue
        valor = valores[0].get("value")
        if isinstance(valor, (int, float)):
            normalizado[nome] = valor
    return normalizado


def _div(a, b, casas=4):
    """Divisão segura: retorna None se faltar dado ou divisor for zero."""
    if a is None or not b:
        return None
    return round(a / b, casas)


def metricas_derivadas(m):
    """
    Métricas derivadas a partir de um dicionário/objeto com os campos base.
    `reels_skip_rate` já vem em porcentagem da Meta e é apenas repassada.
    """
    def g(campo):
        return m.get(campo) if isinstance(m, dict) else getattr(m, campo, None)

    reach = g("reach")
    avg_ms = g("avg_watch_time_ms")
    total_ms = g("total_watch_time_ms")
    return {
        "engagement_by_reach": _div(g("total_interactions"), reach),
        "like_rate": _div(g("likes"), reach),
        "comment_rate": _div(g("comments"), reach),
        "share_rate": _div(g("shares"), reach),
        "save_rate": _div(g("saved"), reach),
        "repost_rate": _div(g("reposts"), reach),
        "views_per_reached_account": _div(g("views"), reach),
        "avg_watch_time_seconds": round(avg_ms / 1000, 3) if avg_ms is not None else None,
        "total_watch_time_seconds": round(total_ms / 1000, 1) if total_ms is not None else None,
        "skip_rate_3s": g("reels_skip_rate"),
    }
