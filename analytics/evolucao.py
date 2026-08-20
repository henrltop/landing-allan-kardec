"""
Análise temporal de uma publicação a partir dos snapshots.

Marcos: snapshot mais próximo de 1h, 3h, 6h, 12h, 24h, 48h, 72h e 7 dias
após a publicação, com tolerância — sem depender do job rodar no minuto exato.
"""
from datetime import timedelta

MARCOS = [
    ("1h", timedelta(hours=1)),
    ("3h", timedelta(hours=3)),
    ("6h", timedelta(hours=6)),
    ("12h", timedelta(hours=12)),
    ("24h", timedelta(hours=24)),
    ("48h", timedelta(hours=48)),
    ("72h", timedelta(hours=72)),
    ("7d", timedelta(days=7)),
]
# Tolerância proporcional: aceita o snapshot mais próximo até 50% do marco
# (mín. 30 minutos), para mais ou para menos.
TOLERANCIA_MINIMA = timedelta(minutes=30)

CAMPOS_CURVA = ["views", "reach", "likes", "comments", "shares", "reposts", "total_interactions"]


def snapshots_ordenados(media):
    return list(media.metrics.order_by("collected_at"))


def snapshot_mais_proximo(media, delta_alvo, snapshots=None):
    """Snapshot mais próximo de published_at + delta_alvo, dentro da tolerância."""
    snaps = snapshots if snapshots is not None else snapshots_ordenados(media)
    if not snaps:
        return None
    alvo = media.published_at + delta_alvo
    melhor = min(snaps, key=lambda s: abs(s.collected_at - alvo))
    tolerancia = max(TOLERANCIA_MINIMA, delta_alvo * 0.5)
    return melhor if abs(melhor.collected_at - alvo) <= tolerancia else None


def marcos_da_midia(media, snapshots=None):
    """{'1h': snapshot|None, '3h': ..., ...}"""
    snaps = snapshots if snapshots is not None else snapshots_ordenados(media)
    return {rotulo: snapshot_mais_proximo(media, delta, snaps) for rotulo, delta in MARCOS}


def crescimento(anterior, atual, campo):
    """(absoluto, percentual) entre dois snapshots para um campo. None-safe."""
    v0 = getattr(anterior, campo, None)
    v1 = getattr(atual, campo, None)
    if v0 is None or v1 is None:
        return None, None
    absoluto = v1 - v0
    percentual = round(absoluto / v0 * 100, 2) if v0 else None
    return absoluto, percentual


def taxa_por_hora(anterior, atual, campo):
    """Variação por hora de um campo entre dois snapshots. None-safe."""
    absoluto, _ = crescimento(anterior, atual, campo)
    if absoluto is None:
        return None
    horas = (atual.collected_at - anterior.collected_at).total_seconds() / 3600
    return round(absoluto / horas, 2) if horas > 0 else None


def curva(media):
    """
    Série temporal completa da publicação:
    [{collected_at, horas_desde_publicacao, views, ..., views_por_hora, ...}]
    """
    snaps = snapshots_ordenados(media)
    serie = []
    for i, snap in enumerate(snaps):
        ponto = {
            "collected_at": snap.collected_at,
            "horas_desde_publicacao": round(
                (snap.collected_at - media.published_at).total_seconds() / 3600, 2),
        }
        for campo in CAMPOS_CURVA:
            ponto[campo] = getattr(snap, campo, None)
        if i > 0:
            ponto["views_por_hora"] = taxa_por_hora(snaps[i - 1], snap, "views")
            ponto["interacoes_por_hora"] = taxa_por_hora(snaps[i - 1], snap, "total_interactions")
        serie.append(ponto)
    return serie


def resumo_crescimento(media):
    """Crescimento total (primeiro → último snapshot) dos campos principais."""
    snaps = snapshots_ordenados(media)
    if len(snaps) < 2:
        return {}
    primeiro, ultimo = snaps[0], snaps[-1]
    resultado = {}
    for campo in CAMPOS_CURVA:
        absoluto, percentual = crescimento(primeiro, ultimo, campo)
        resultado[campo] = {"absoluto": absoluto, "percentual": percentual}
    return resultado
