"""
Testes do módulo Instagram Analytics. A Meta Graph API é sempre mockada —
nenhum teste depende da API real ou do token.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .client import MetaAPIError, MetaInstagramClient
from .evolucao import crescimento, snapshot_mais_proximo, taxa_por_hora
from .metrics_config import REELS_METRICS, SAFE_METRICS
from .models import InstagramMedia, InstagramMediaMetrics
from .normalize import metricas_derivadas, normalizar_insights

CONFIG_TESTE = dict(META_PAGE_ACCESS_TOKEN="token-de-teste",
                    INSTAGRAM_ACCOUNT_ID="123", META_GRAPH_API_VERSION="v26.0")


def resposta(status=200, corpo=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = corpo or {}
    return m


class NormalizacaoTests(TestCase):
    def test_normaliza_formato_cru_da_meta(self):
        cru = [
            {"name": "views", "period": "lifetime", "values": [{"value": 2282}]},
            {"name": "ig_reels_avg_watch_time", "values": [{"value": 11766}]},
            {"name": "reels_skip_rate", "values": [{"value": 55.2}]},
            {"name": "metrica_desconhecida", "values": [{"value": 1}]},
            {"name": "reach", "values": []},  # sem valores -> ignorada
        ]
        n = normalizar_insights(cru)
        self.assertEqual(n["views"], 2282)
        self.assertEqual(n["avg_watch_time_ms"], 11766)
        self.assertEqual(n["reels_skip_rate"], 55.2)
        self.assertNotIn("metrica_desconhecida", n)
        self.assertNotIn("reach", n)

    def test_derivadas_com_divisao_por_zero(self):
        d = metricas_derivadas({"total_interactions": 10, "likes": 5, "reach": 0,
                                "views": None, "avg_watch_time_ms": None})
        self.assertIsNone(d["engagement_by_reach"])
        self.assertIsNone(d["like_rate"])
        self.assertIsNone(d["avg_watch_time_seconds"])

    def test_derivadas_valores_corretos(self):
        d = metricas_derivadas({"total_interactions": 410, "reach": 1474, "likes": 230,
                                "comments": 100, "shares": 38, "saved": 0, "reposts": 42,
                                "views": 2282, "avg_watch_time_ms": 11766,
                                "total_watch_time_ms": 18167432, "reels_skip_rate": 55.2})
        self.assertAlmostEqual(d["engagement_by_reach"], 0.2782, places=4)
        self.assertAlmostEqual(d["share_rate"], 0.0258, places=4)
        self.assertEqual(d["avg_watch_time_seconds"], 11.766)
        self.assertEqual(d["skip_rate_3s"], 55.2)  # repassada, nunca recalculada


@override_settings(**CONFIG_TESTE)
class ClienteTests(TestCase):
    @patch("analytics.client.requests.get")
    def test_paginacao_segue_cursor(self, get):
        get.side_effect = [
            resposta(200, {"data": [{"id": "1"}, {"id": "2"}],
                           "paging": {"cursors": {"after": "CUR"}, "next": "http://x"}}),
            resposta(200, {"data": [{"id": "3"}], "paging": {}}),
        ]
        ids = [m["id"] for m in MetaInstagramClient().midias()]
        self.assertEqual(ids, ["1", "2", "3"])
        self.assertEqual(get.call_args_list[1].kwargs["params"]["after"], "CUR")

    @patch("analytics.client.time.sleep")
    @patch("analytics.client.requests.get")
    def test_retry_em_erro_5xx(self, get, _sleep):
        get.side_effect = [resposta(500, {"error": {"message": "boom"}}),
                           resposta(200, {"id": "123", "username": "x"})]
        perfil = MetaInstagramClient().perfil()
        self.assertEqual(perfil["id"], "123")
        self.assertEqual(get.call_count, 2)

    @patch("analytics.client.time.sleep")
    @patch("analytics.client.requests.get")
    def test_retry_nao_e_infinito(self, get, _sleep):
        get.return_value = resposta(429, {"error": {"message": "rate limit", "code": 4}})
        with self.assertRaises(MetaAPIError):
            MetaInstagramClient().perfil()
        self.assertLessEqual(get.call_count, 5)

    @patch("analytics.client.requests.get")
    def test_fallback_para_metricas_seguras_no_erro_100(self, get):
        get.side_effect = [
            resposta(400, {"error": {"message": "metric incompativel", "code": 100,
                                     "type": "OAuthException"}}),
            resposta(200, {"data": [{"name": "reach", "values": [{"value": 9}]}]}),
        ]
        crus, usadas = MetaInstagramClient().insights("m1", REELS_METRICS)
        self.assertEqual(usadas, SAFE_METRICS)
        self.assertEqual(crus[0]["name"], "reach")

    @patch("analytics.client.requests.get")
    def test_erro_nao_contem_token(self, get):
        get.return_value = resposta(400, {"error": {
            "message": "Token token-de-teste invalido", "code": 190, "type": "OAuthException"}})
        with self.assertRaises(MetaAPIError) as ctx:
            MetaInstagramClient().perfil()
        self.assertNotIn("token-de-teste", str(ctx.exception))
        self.assertTrue(ctx.exception.token_invalido)

    def test_config_ausente_impede_inicio(self):
        with override_settings(META_PAGE_ACCESS_TOKEN=""):
            with self.assertRaises(MetaAPIError):
                MetaInstagramClient()


def _mock_cliente(midias=None, insights=None):
    cliente = MagicMock()
    cliente.requests_feitas = 0
    cliente.perfil.return_value = {"id": "123", "username": "conta", "name": "Conta",
                                   "followers_count": 100, "media_count": 2}
    cliente.midias.return_value = iter(midias or [])
    cliente.insights.return_value = (insights or [
        {"name": "views", "values": [{"value": 50}]},
        {"name": "reach", "values": [{"value": 40}]},
    ], REELS_METRICS)
    return cliente


MIDIA_EXEMPLO = {"id": "M1", "caption": "Oi", "media_type": "VIDEO",
                 "media_product_type": "REELS", "permalink": "https://ig/x",
                 "timestamp": "2026-08-20T10:00:00+0000", "like_count": 5, "comments_count": 1}


@override_settings(**CONFIG_TESTE)
class SincronizacaoTests(TestCase):
    @patch("analytics.sync.MetaInstagramClient")
    def test_coleta_cria_midia_e_snapshot(self, Cliente):
        from .sync import sincronizar
        Cliente.return_value = _mock_cliente([MIDIA_EXEMPLO])
        run = sincronizar(since="2026-08-01")
        self.assertEqual(run.status, "sucesso")
        self.assertEqual(run.media_discovered, 1)
        self.assertEqual(run.snapshots_created, 1)
        snap = InstagramMedia.objects.get(instagram_media_id="M1").ultimo_snapshot
        self.assertEqual(snap.views, 50)
        self.assertEqual(snap.raw_response[0]["name"], "views")

    @patch("analytics.sync.MetaInstagramClient")
    def test_upsert_nao_duplica_midia(self, Cliente):
        from .sync import sincronizar
        Cliente.return_value = _mock_cliente([MIDIA_EXEMPLO])
        sincronizar(since="2026-08-01")
        Cliente.return_value = _mock_cliente([dict(MIDIA_EXEMPLO, like_count=9)])
        sincronizar(since="2026-08-01")
        self.assertEqual(InstagramMedia.objects.count(), 1)
        self.assertEqual(InstagramMedia.objects.get().like_count, 9)

    @patch("analytics.sync.MetaInstagramClient")
    def test_dedupe_de_snapshot_na_mesma_janela(self, Cliente):
        from .sync import sincronizar
        Cliente.return_value = _mock_cliente([MIDIA_EXEMPLO])
        sincronizar(since="2026-08-01")
        Cliente.return_value = _mock_cliente([MIDIA_EXEMPLO])
        sincronizar(since="2026-08-01")  # logo em seguida -> dedupe de 10min segura
        self.assertEqual(InstagramMediaMetrics.objects.count(), 1)
        Cliente.return_value = _mock_cliente([MIDIA_EXEMPLO])
        sincronizar(since="2026-08-01", forcar_snapshot=True)  # forcar ignora
        self.assertEqual(InstagramMediaMetrics.objects.count(), 2)

    @patch("analytics.sync.MetaInstagramClient")
    def test_erro_em_uma_midia_nao_impede_as_demais(self, Cliente):
        from .sync import sincronizar
        cliente = _mock_cliente([MIDIA_EXEMPLO, dict(MIDIA_EXEMPLO, id="M2")])
        cliente.insights.side_effect = [
            MetaAPIError("sem insights", codigo=100),
            ([{"name": "views", "values": [{"value": 7}]}], REELS_METRICS),
        ]
        Cliente.return_value = cliente
        run = sincronizar(since="2026-08-01")
        self.assertEqual(run.status, "parcial")
        self.assertEqual(run.snapshots_created, 1)
        self.assertEqual(run.errors_count, 1)
        self.assertIn("M1", run.error_summary)


class EvolucaoTests(TestCase):
    def setUp(self):
        self.media = InstagramMedia.objects.create(
            instagram_media_id="M1", media_type="VIDEO", media_product_type="REELS",
            published_at=timezone.now() - timedelta(days=2))

    def _snap(self, horas_apos, views):
        s = InstagramMediaMetrics.objects.create(media=self.media, views=views, reach=views)
        # ajusta collected_at manualmente (auto_now_add)
        InstagramMediaMetrics.objects.filter(pk=s.pk).update(
            collected_at=self.media.published_at + timedelta(hours=horas_apos))
        return InstagramMediaMetrics.objects.get(pk=s.pk)

    def test_snapshot_mais_proximo_respeita_tolerancia(self):
        self._snap(1.2, 1000)   # perto de 1h (dentro de 30min)
        self._snap(30, 5000)    # perto de 24h? 30h com tolerancia 12h -> aceita
        self.assertEqual(snapshot_mais_proximo(self.media, timedelta(hours=1)).views, 1000)
        self.assertEqual(snapshot_mais_proximo(self.media, timedelta(hours=24)).views, 5000)
        # 7 dias: nenhum snapshot dentro de 3.5 dias do alvo
        self.assertIsNone(snapshot_mais_proximo(self.media, timedelta(days=7)))

    def test_crescimento_e_taxa_por_hora(self):
        a = self._snap(1, 1000)
        b = self._snap(3, 2800)
        absoluto, percentual = crescimento(a, b, "views")
        self.assertEqual(absoluto, 1800)
        self.assertEqual(percentual, 180.0)
        self.assertEqual(taxa_por_hora(a, b, "views"), 900.0)

    def test_crescimento_none_safe(self):
        a = self._snap(1, 1000)
        b = InstagramMediaMetrics.objects.create(media=self.media)  # sem views
        self.assertEqual(crescimento(a, b, "views"), (None, None))
        self.assertIsNone(taxa_por_hora(a, b, "views"))


@override_settings(**CONFIG_TESTE)
class ColetaAmpliadaTests(TestCase):
    @patch("analytics.sync.MetaInstagramClient")
    def test_diarios_upsert_por_data(self, Cliente):
        from .models import InstagramAccountDailyInsight
        from .sync import sincronizar
        cliente = _mock_cliente([])
        cliente.insights_diarios.return_value = [
            {"name": "follower_count", "values": [
                {"end_time": "2026-08-18T07:00:00+0000", "value": 50},
                {"end_time": "2026-08-19T07:00:00+0000", "value": 12}]},
            {"name": "reach", "values": [
                {"end_time": "2026-08-18T07:00:00+0000", "value": 9000}]},
        ]
        cliente.stories.return_value = iter([])
        Cliente.return_value = cliente
        sincronizar(since="2026-08-01")
        # segunda execucao com valor consolidado -> atualiza, nao duplica
        cliente2 = _mock_cliente([])
        cliente2.insights_diarios.return_value = [
            {"name": "follower_count", "values": [
                {"end_time": "2026-08-19T07:00:00+0000", "value": 47}]},
        ]
        cliente2.stories.return_value = iter([])
        Cliente.return_value = cliente2
        sincronizar(since="2026-08-01")
        self.assertEqual(InstagramAccountDailyInsight.objects.count(), 2)
        dia = InstagramAccountDailyInsight.objects.get(date="2026-08-19")
        self.assertEqual(dia.new_followers, 47)
        d18 = InstagramAccountDailyInsight.objects.get(date="2026-08-18")
        self.assertEqual((d18.new_followers, d18.reach), (50, 9000))

    @patch("analytics.sync.MetaInstagramClient")
    def test_stories_snapshot_e_dedupe(self, Cliente):
        from .models import InstagramStory, InstagramStoryMetrics
        from .sync import sincronizar
        story = {"id": "S1", "media_type": "IMAGE", "permalink": "",
                 "timestamp": "2026-08-20T10:00:00+0000"}
        cliente = _mock_cliente([])
        cliente.insights_diarios.return_value = []
        cliente.stories.return_value = iter([story])
        cliente.insights.return_value = ([
            {"name": "views", "values": [{"value": 49}]},
            {"name": "navigation", "values": [{"value": 17}]},
        ], [])
        Cliente.return_value = cliente
        run = sincronizar(since="2026-08-01")
        self.assertEqual(run.stories_snapshots, 1)
        snap = InstagramStory.objects.get(instagram_media_id="S1").ultimo_snapshot
        self.assertEqual((snap.views, snap.navigation), (49, 17))
        # repeticao imediata -> dedupe de 10 min segura o snapshot
        cliente.stories.return_value = iter([story])
        sincronizar(since="2026-08-01")
        self.assertEqual(InstagramStoryMetrics.objects.count(), 1)


class ExportAsOfTests(TestCase):
    def test_snapshot_as_of_respeita_fim_do_periodo(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import InstagramMedia, InstagramMediaMetrics
        from .views import _snapshot_as_of
        m = InstagramMedia.objects.create(
            instagram_media_id="M1", media_type="VIDEO", media_product_type="REELS",
            published_at=timezone.now() - timedelta(days=3))
        antigo = InstagramMediaMetrics.objects.create(media=m, views=100)
        InstagramMediaMetrics.objects.filter(pk=antigo.pk).update(
            collected_at=timezone.now() - timedelta(days=2))
        novo = InstagramMediaMetrics.objects.create(media=m, views=900)
        fim = timezone.now() - timedelta(days=1)
        self.assertEqual(_snapshot_as_of(m, fim).views, 100)   # estado de "ontem"
        self.assertEqual(_snapshot_as_of(m, None).views, 900)  # atual
