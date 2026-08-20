"""
MetaInstagramClient — cliente centralizado da Meta Graph API.

Responsável por autenticação, requisições, paginação, timeout, retry com
backoff exponencial, normalização de erros, rate limit e logging.
O token NUNCA aparece em logs, exceções ou retornos.
"""
import logging
import time

import requests
from django.conf import settings

from . import metrics_config

logger = logging.getLogger("analytics.meta")

TIMEOUT = 30           # segundos por requisição
MAX_RETRIES = 4        # tentativas para 429/5xx/erros de rede
BACKOFF_BASE = 2       # espera 2s, 4s, 8s...
MAX_PAGES = 200        # trava de segurança na paginação


class MetaAPIError(Exception):
    """Erro normalizado da Meta. Nunca contém o token."""

    def __init__(self, mensagem, codigo=None, subcodigo=None, http_status=None,
                 tipo=None, retryable=False):
        super().__init__(mensagem)
        self.codigo = codigo
        self.subcodigo = subcodigo
        self.http_status = http_status
        self.tipo = tipo
        self.retryable = retryable

    @property
    def metrica_incompativel(self):
        return self.codigo == 100

    @property
    def token_invalido(self):
        return self.codigo == 190 or self.tipo == "OAuthException" and self.codigo in (102, 190)


def _redigir(texto):
    """Remove o token de qualquer string que possa ir para log."""
    token = settings.META_PAGE_ACCESS_TOKEN
    if token and token in str(texto):
        return str(texto).replace(token, "TOKEN_REDIGIDO")
    return str(texto)


class MetaInstagramClient:
    def __init__(self):
        self.base = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"
        self.requests_feitas = 0
        self._validar_config()

    @staticmethod
    def _validar_config():
        faltando = [nome for nome in
                    ("META_PAGE_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID", "META_GRAPH_API_VERSION")
                    if not getattr(settings, nome)]
        if faltando:
            raise MetaAPIError(
                f"Configuração ausente: {', '.join(faltando)}. "
                "Defina as variáveis de ambiente (ver .env.example)."
            )

    # ---------- núcleo de requisição ----------
    def _get(self, caminho, params=None):
        params = dict(params or {})
        params["access_token"] = settings.META_PAGE_ACCESS_TOKEN
        url = f"{self.base}/{caminho}"

        ultimo_erro = None
        for tentativa in range(1, MAX_RETRIES + 1):
            try:
                resposta = requests.get(url, params=params, timeout=TIMEOUT)
                self.requests_feitas += 1
            except requests.RequestException as exc:
                ultimo_erro = MetaAPIError(f"Falha de rede: {_redigir(exc)}", retryable=True)
                logger.warning("Rede (tentativa %s/%s): %s", tentativa, MAX_RETRIES, _redigir(exc))
                time.sleep(BACKOFF_BASE ** tentativa)
                continue

            if resposta.status_code == 200:
                return resposta.json()

            erro = self._normalizar_erro(resposta)
            if erro.retryable and tentativa < MAX_RETRIES:
                espera = BACKOFF_BASE ** tentativa
                logger.warning("HTTP %s (tentativa %s/%s), aguardando %ss: %s",
                               resposta.status_code, tentativa, MAX_RETRIES, espera, erro)
                time.sleep(espera)
                ultimo_erro = erro
                continue
            raise erro

        raise ultimo_erro or MetaAPIError("Falha desconhecida após retries")

    @staticmethod
    def _normalizar_erro(resposta):
        try:
            corpo = resposta.json().get("error", {})
        except ValueError:
            corpo = {}
        mensagem = _redigir(corpo.get("message", f"HTTP {resposta.status_code}"))
        codigo = corpo.get("code")
        tipo = corpo.get("type")
        retryable = resposta.status_code == 429 or resposta.status_code >= 500 or codigo in (4, 17, 32, 613)
        return MetaAPIError(
            mensagem, codigo=codigo, subcodigo=corpo.get("error_subcode"),
            http_status=resposta.status_code, tipo=tipo, retryable=retryable,
        )

    # ---------- paginação ----------
    def _paginar(self, caminho, params, max_itens=None):
        """Itera todas as páginas usando o cursor 'after' da Meta."""
        coletados = 0
        pagina = 0
        while pagina < MAX_PAGES:
            pagina += 1
            dados = self._get(caminho, params)
            itens = dados.get("data", [])
            for item in itens:
                yield item
                coletados += 1
                if max_itens and coletados >= max_itens:
                    return
            cursor = dados.get("paging", {}).get("cursors", {}).get("after")
            proxima = dados.get("paging", {}).get("next")
            if not itens or not proxima or not cursor:
                return
            params = dict(params)
            params["after"] = cursor
        logger.warning("Paginação interrompida na trava de %s páginas", MAX_PAGES)

    # ---------- API pública do cliente ----------
    def perfil(self):
        """Dados básicos do perfil (snapshot de seguidores)."""
        return self._get(
            settings.INSTAGRAM_ACCOUNT_ID,
            {"fields": ",".join(metrics_config.PROFILE_FIELDS)},
        )

    def midias(self, since=None, until=None, max_itens=None, fields=None):
        """Publicações da conta, com paginação completa e filtro por período."""
        params = {"fields": ",".join(fields or metrics_config.MEDIA_FIELDS), "limit": 100}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        yield from self._paginar(f"{settings.INSTAGRAM_ACCOUNT_ID}/media", params, max_itens)

    def stories(self):
        """Stories ativas (a Meta só expõe enquanto estão no ar, ~24h)."""
        params = {"fields": "id,media_type,permalink,timestamp", "limit": 100}
        yield from self._paginar(f"{settings.INSTAGRAM_ACCOUNT_ID}/stories", params)

    def insights_diarios(self, since, until):
        """Métricas diárias da conta (follower_count/reach), retroativas até ~30 dias."""
        dados = self._get(f"{settings.INSTAGRAM_ACCOUNT_ID}/insights", {
            "metric": ",".join(metrics_config.DAILY_METRICS),
            "period": "day", "since": since, "until": until,
        })
        return dados.get("data", [])

    def insights(self, media_id, metricas):
        """
        Insights de uma mídia. Se a Meta rejeitar o conjunto (#100),
        faz fallback para SAFE_METRICS e registra claramente.
        Retorna (lista_crua, metricas_usadas).
        """
        try:
            dados = self._get(f"{media_id}/insights", {"metric": ",".join(metricas)})
            return dados.get("data", []), list(metricas)
        except MetaAPIError as erro:
            if erro.metrica_incompativel and list(metricas) != metrics_config.SAFE_METRICS:
                logger.warning("Mídia %s: métricas incompatíveis (%s). Fallback para conjunto seguro.",
                               media_id, erro)
                dados = self._get(f"{media_id}/insights",
                                  {"metric": ",".join(metrics_config.SAFE_METRICS)})
                return dados.get("data", []), list(metrics_config.SAFE_METRICS)
            raise
