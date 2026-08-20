# Instagram Analytics — módulo de coleta e histórico

Coleta, armazena histórico e disponibiliza métricas do Instagram oficial da
campanha usando exclusivamente a **Meta Graph API** (v26.0). Base preparada
para análise posterior por IA.

## Configuração

Variáveis de ambiente (ver `.env.example`; o `.env` é ignorado pelo git):

```env
META_GRAPH_API_VERSION=v26.0
META_PAGE_ACCESS_TOKEN=...   # confidencial — nunca commitar/logar/expor
INSTAGRAM_ACCOUNT_ID=17841404731251423
META_PAGE_ID=402554383123636
```

O coletor valida a configuração na inicialização e se recusa a rodar sem as
variáveis (sem exibir valores). O token nunca aparece em logs, exceções,
endpoints ou frontend (redação automática em `client._redigir`).

## Arquitetura

| Arquivo | Papel |
|---|---|
| `metrics_config.py` | Fonte única das métricas por tipo (REELS/FEED/SAFE) e campos |
| `client.py` | `MetaInstagramClient`: auth, paginação por cursor, retry/backoff (429/5xx), normalização de erros, fallback #100 |
| `normalize.py` | Formato cru da Meta → dicionário plano + métricas derivadas (divisão por zero → `None`) |
| `sync.py` | Orquestração: perfil → mídias → insights → snapshots + log da execução |
| `evolucao.py` | Curvas temporais, marcos (1h…7d com tolerância), crescimento, taxas/hora |
| `models.py` | `InstagramAccountSnapshot`, `InstagramMedia`, `InstagramMediaMetrics`, `InstagramCollectionRun` |

**Snapshots nunca são sobrescritos** — cada coleta cria um novo registro em
`InstagramMediaMetrics` (com o JSON cru em `raw_response` para auditoria).
`reels_skip_rate` é a porcentagem oficial da Meta (abandono nos 3 primeiros
segundos) e é apenas repassada, nunca recalculada.

## Comandos

```bash
# backfill por período (recomendado para começar)
python manage.py instagram_sync --since 2026-08-15
python manage.py instagram_sync --since 2026-08-01 --until 2026-08-10
python manage.py instagram_sync --max 50

# backfill completo (milhares de mídias — usar com consciência)
python manage.py instagram_sync --full

# forçar snapshot fora da janela de frequência
python manage.py instagram_sync --since 2026-08-15 --forcar

# testar uma única mídia (mostra normalizado + derivadas)
python manage.py instagram_sync_media 18631351960043833
```

## Estratégia de atualização (economia de API)

Definida em `sync.FAIXAS_ATUALIZACAO`:

| Idade da publicação | Novo snapshot no máximo a cada |
|---|---|
| até 48h | ~1h (toda execução) |
| 3–7 dias | 6h |
| até 30 dias | 48h |
| mais antigas | 7 dias |

Dedupe de segurança: nunca dois snapshots da mesma mídia em menos de 10 min.

## Job automático (produção)

Padrão do projeto é cron na VM. Sugestão (a cada hora, janela móvel de 14 dias):

```cron
0 * * * * www-data cd /caminho/do/projeto && venv/bin/python manage.py instagram_sync --since $(date -d '14 days ago' +\%Y-\%m-\%d) >> /var/log/instagram-sync.log 2>&1
```

As execuções ficam registradas em `InstagramCollectionRun` e aparecem no topo
do dashboard (status, snapshots, requests, erros) — sem precisar de terminal.

## Interface e API

- **Dashboard**: `/painel/instagram/` (login do painel) — visão geral com
  seguidores e crescimento, totais, filtros (período/tipo), ranking ordenável
  (views, alcance, interações, shares, reposts, comentários, menor skip rate,
  maior watch time).
- **Detalhe**: `/painel/instagram/<id>/` — métricas atuais + derivadas,
  gráfico SVG da evolução de views, marcos temporais e todos os snapshots.
- **API p/ IA**: `GET /api/analytics/instagram/media?inicio=&fim=&tipo=` (JSON)
- **Export**: `GET /api/analytics/instagram/export?formato=csv|json`

Campos reservados para classificação futura por IA já existem no modelo e na
API (`tema`, `subtema`, `cidade`, `resumo`) — hoje sempre `null`.

## Comentários (futuro)

Hoje coletamos apenas `comments_count`. A leitura dos textos dos comentários
exigirá permissões adicionais; o cliente centralizado permite acrescentar um
método `comentarios(media_id)` sem tocar no resto do sistema.

## Testes

```bash
python manage.py test analytics
```

16 testes com a API mockada: normalização, derivadas (divisão por zero),
paginação, retry limitado, fallback #100, redação do token em erros,
validação de config, snapshots/dedupe, upsert, resiliência por mídia e
funções de evolução.
