"""
Configuração central de métricas por tipo de mídia (Meta Graph API v26.0).

Única fonte de verdade — nunca espalhar listas de métricas pelo código.
Validadas em produção para esta conta em ago/2026. NÃO usar
clips_replays_count nem ig_reels_aggregated_all_plays_count (erro #100).
"""

# Reels (media_product_type == "REELS")
REELS_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
    "ig_reels_video_view_total_time",
    "ig_reels_avg_watch_time",
    "reels_skip_rate",
    "reposts",
]

# Conjunto seguro para FEED (imagens/carrossel/vídeo de feed).
# Métricas de watch time e skip rate são exclusivas de Reels.
FEED_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
]

# Stories (validado ao vivo em ago/2026; "impressions" não existe mais na v22+)
STORY_METRICS = [
    "views",
    "reach",
    "replies",
    "shares",
    "total_interactions",
    "navigation",
]

# Insights diários da conta (retroativos até ~30 dias)
DAILY_METRICS = ["follower_count", "reach"]

# Fallback mínimo caso a Meta rejeite alguma métrica (#100):
# conjunto que funciona para qualquer tipo de mídia com insights.
SAFE_METRICS = [
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
]

# Tradução dos nomes crus da Meta para os campos normalizados do sistema
NORMALIZED_NAMES = {
    "views": "views",
    "reach": "reach",
    "likes": "likes",
    "comments": "comments",
    "saved": "saved",
    "shares": "shares",
    "total_interactions": "total_interactions",
    "ig_reels_video_view_total_time": "total_watch_time_ms",
    "ig_reels_avg_watch_time": "avg_watch_time_ms",
    "reels_skip_rate": "reels_skip_rate",
    "reposts": "reposts",
}

# Campos pedidos na listagem de mídias
MEDIA_FIELDS = [
    "id",
    "caption",
    "media_type",
    "media_product_type",
    "permalink",
    "timestamp",
    "like_count",
    "comments_count",
    "thumbnail_url",
    "media_url",
]

PROFILE_FIELDS = ["id", "username", "name", "followers_count", "media_count"]


def metrics_para_midia(media_type, media_product_type):
    """Retorna a lista de métricas adequada ao tipo de publicação."""
    if media_product_type == "REELS":
        return REELS_METRICS
    return FEED_METRICS
