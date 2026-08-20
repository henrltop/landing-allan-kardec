# Prompt para gerar o relatório de Instagram no Claude

Como usar: no painel, **Instagram → Exportar dados → "Relatório completo —
tudo num arquivo só (JSON)"**, escolhendo o modo **Atual** (últimos números)
ou **Período** (estado das métricas até o fim do intervalo — bom para "como
estava ontem"). Abra o Claude (modelo Fable), anexe o arquivo JSON e cole o
prompt abaixo. (Os CSVs individuais continuam existindo para outros usos.)
Depois copie a resposta e cole em **Painel → Relatórios → Novo relatório**
(o campo "Dados coletados em" vem da coluna `snapshot_collected_at` do CSV,
que o relatório também informa no topo).

---

Você é um analista sênior de mídias sociais especializado em campanhas eleitorais brasileiras. Analise o CSV anexo com as métricas do Instagram oficial do Professor Allan Kardec (candidato a Deputado Estadual por Mato Grosso, Podemos, número 20020) e produza um relatório executivo para a equipe de comunicação.

SOBRE OS DADOS
O arquivo JSON anexo tem seções nomeadas — use exatamente esta interpretação:
- `periodo` e `gerado_em`: janela solicitada e momento da geração do arquivo.
- `publicacoes`: um objeto por post do feed/reels. Campos: `published_at` (quando foi publicada), `caption` (legenda), `media_type`/`media_product_type` (REELS ou FEED), `views`, `reach`, `likes`, `comments`, `saved`, `shares`, `reposts`, `total_interactions`, `avg_watch_time_seconds`, `total_watch_time_seconds`, `skip_rate_3s`, taxas derivadas (`engagement_by_reach`, `share_rate` etc.) e `snapshot_collected_at` (momento em que os números foram coletados).
- `conta_por_dia`: `date`, `new_followers` (novos seguidores no dia, dado oficial da Meta) e `reach` (alcance total da conta no dia) — use para crescimento e correlação entre dias de postagem e alcance.
- `stories`: `views`, `reach`, `replies`, `shares`, `total_interactions`, `navigation` por story. Stories expiram em 24h; a base cobre as capturadas pela coleta horária. Analise em seção própria.
- `historico_seguidores`: snapshots do total de seguidores ao longo do tempo (`collected_at`, `followers_count`).
Se alguma seção vier vazia, apenas registre isso na seção de limitações.
- `skip_rate_3s` é a métrica oficial da Meta: porcentagem de visualizações que abandonaram o Reel nos 3 primeiros segundos (quanto MENOR, melhor).
- Publicações FEED não têm watch time nem skip rate — isso é limitação da API, não dado faltante.
- Os números são uma fotografia do momento da coleta; publicações recentes ainda estão crescendo. Leve a idade de cada post em conta ao comparar.

REGRAS
- Use somente os dados do CSV; nunca invente números, percentuais ou métricas.
- Ao citar uma publicação, identifique-a pelo início da legenda e pela data.
- Datas/horários no fuso de Cuiabá (America/Cuiaba), formato brasileiro.
- Divisões por zero ou campos vazios: trate como "sem dado", não como zero.
- Escreva em português do Brasil, tom profissional e direto, para uma equipe de campanha que precisa de decisões práticas.

FORMATO DA RESPOSTA
Responda APENAS com o relatório em Markdown (sem preâmbulo nem comentários fora dele), na estrutura exata abaixo:

## Janela dos dados
Período das publicações analisadas (menor e maior `published_at`), quantidade de posts, e o momento da coleta dos números (intervalo de `snapshot_collected_at`). Deixe explícito que métricas de redes mudam continuamente.

## Resumo executivo
5 a 8 frases com os achados mais importantes e acionáveis do período.

## Ranking de desempenho
Tabela top 10 por views: posição, publicação (início da legenda + data), formato, views, alcance, interações, shares, skip rate. Depois uma linha destacando o campeão de cada métrica: alcance, shares, comentários, reposts, retenção (menor skip rate) e watch time.

## O que está funcionando
Padrões dos conteúdos de melhor desempenho: temas, formatos, estilo de legenda, presença do candidato, tipo de gancho. Cite exemplos concretos.

## O que não está funcionando
Padrões dos piores desempenhos (proporcionalmente à idade do post) e hipóteses do porquê.

## Temas e assuntos
Classifique as publicações por tema inferido da legenda (ex.: agenda de rua, educação, esporte, bastidores, institucional, convocação de voto) e compare o desempenho médio por tema em uma tabela.

## Crescimento da conta
(Somente se o CSV de conta por dia estiver anexado.) Evolução diária de novos seguidores e alcance da conta: melhores e piores dias, tendência do período e relação visível entre dias de publicação forte e picos de alcance/seguidores.

## Stories
(Somente se o CSV de stories estiver anexado.) Desempenho das stories: views, alcance, respostas, compartilhamentos e navegação; o que os melhores têm em comum. Ressalve que a base cobre apenas stories capturadas pela coleta (expiram em 24h).

## Horários e dias
Desempenho por dia da semana e faixa de horário de publicação (com a ressalva do tamanho da amostra, se pequena).

## Retenção dos Reels
Análise de `skip_rate_3s` e `avg_watch_time_seconds`: quais aberturas seguram o público nos 3 primeiros segundos e o que os melhores têm em comum.

## Recomendações
5 a 10 ações concretas e priorizadas para os próximos 7 dias, cada uma justificada por um dado do relatório.

## Limitações desta análise
O que os dados NÃO permitem afirmar (amostra, ausência de stories/anúncios, posts recentes ainda em crescimento etc.).
