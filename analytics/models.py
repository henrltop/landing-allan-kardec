from django.db import models


class InstagramAccountSnapshot(models.Model):
    """Histórico do perfil — um registro por coleta, nunca sobrescrito."""
    instagram_account_id = models.CharField(max_length=32)
    username = models.CharField(max_length=120)
    name = models.CharField(max_length=200, blank=True)
    followers_count = models.BigIntegerField()
    media_count = models.BigIntegerField()
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Snapshot do perfil"
        ordering = ["-collected_at"]

    def __str__(self):
        return f"@{self.username} · {self.followers_count} seguidores · {self.collected_at:%d/%m %H:%M}"


class InstagramMedia(models.Model):
    """Publicação do Instagram (metadados; métricas ficam nos snapshots)."""
    instagram_media_id = models.CharField(max_length=32, unique=True, db_index=True)
    caption = models.TextField(blank=True)
    media_type = models.CharField(max_length=20)             # IMAGE / VIDEO / CAROUSEL_ALBUM
    media_product_type = models.CharField(max_length=20)     # REELS / FEED
    permalink = models.URLField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=1000, blank=True)
    like_count = models.BigIntegerField(null=True, blank=True)      # metadado mais recente
    comments_count = models.BigIntegerField(null=True, blank=True)  # metadado mais recente
    published_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Campos reservados para classificação futura por IA (não preenchidos hoje)
    tema = models.CharField(max_length=60, blank=True)
    subtema = models.CharField(max_length=60, blank=True)
    cidade = models.CharField(max_length=80, blank=True)
    resumo = models.TextField(blank=True)

    class Meta:
        verbose_name = "Publicação do Instagram"
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.instagram_media_id} ({self.media_product_type})"

    @property
    def ultimo_snapshot(self):
        return self.metrics.order_by("-collected_at").first()


class InstagramMediaMetrics(models.Model):
    """Snapshot de métricas de uma publicação em um instante. Nunca sobrescrever."""
    media = models.ForeignKey(InstagramMedia, on_delete=models.CASCADE, related_name="metrics")
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)

    views = models.BigIntegerField(null=True, blank=True)
    reach = models.BigIntegerField(null=True, blank=True)
    likes = models.BigIntegerField(null=True, blank=True)
    comments = models.BigIntegerField(null=True, blank=True)
    saved = models.BigIntegerField(null=True, blank=True)
    shares = models.BigIntegerField(null=True, blank=True)
    reposts = models.BigIntegerField(null=True, blank=True)
    total_interactions = models.BigIntegerField(null=True, blank=True)

    total_watch_time_ms = models.BigIntegerField(null=True, blank=True)
    avg_watch_time_ms = models.BigIntegerField(null=True, blank=True)
    reels_skip_rate = models.FloatField(null=True, blank=True)

    raw_response = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Snapshot de métricas"
        ordering = ["-collected_at"]
        indexes = [models.Index(fields=["media", "collected_at"])]

    def __str__(self):
        return f"{self.media_id} · {self.collected_at:%d/%m %H:%M} · views={self.views}"


class InstagramAccountDailyInsight(models.Model):
    """
    Métricas diárias da conta vindas da própria Meta (retroativas até ~30 dias):
    novos seguidores e alcance por dia. Upsert por data — a Meta consolida os
    números do dia corrente ao longo do dia.
    """
    date = models.DateField("Dia", unique=True, db_index=True)
    new_followers = models.IntegerField("Novos seguidores", null=True, blank=True)
    reach = models.BigIntegerField("Alcance do dia", null=True, blank=True)
    collected_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Métrica diária da conta"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} · +{self.new_followers} seguidores · reach {self.reach}"


class InstagramStory(models.Model):
    """Story publicado (a API só lista stories ativas — coleta horária captura o ciclo)."""
    instagram_media_id = models.CharField(max_length=32, unique=True, db_index=True)
    media_type = models.CharField(max_length=20)
    permalink = models.URLField(max_length=500, blank=True)
    published_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Story"
        verbose_name_plural = "Stories"
        ordering = ["-published_at"]

    def __str__(self):
        return f"Story {self.instagram_media_id} ({self.published_at:%d/%m %H:%M})"

    @property
    def ultimo_snapshot(self):
        return self.metrics.order_by("-collected_at").first()


class InstagramStoryMetrics(models.Model):
    """Snapshot das métricas de um story. Nunca sobrescrever."""
    story = models.ForeignKey(InstagramStory, on_delete=models.CASCADE, related_name="metrics")
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)

    views = models.BigIntegerField(null=True, blank=True)
    reach = models.BigIntegerField(null=True, blank=True)
    replies = models.BigIntegerField(null=True, blank=True)
    shares = models.BigIntegerField(null=True, blank=True)
    total_interactions = models.BigIntegerField(null=True, blank=True)
    navigation = models.BigIntegerField(null=True, blank=True)

    raw_response = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Snapshot de story"
        ordering = ["-collected_at"]
        indexes = [models.Index(fields=["story", "collected_at"])]


class RelatorioAnalise(models.Model):
    """
    Relatório de análise (gerado externamente por IA e colado pela equipe).
    Guarda a janela de dados avaliada — os números mudam rápido, então o
    momento da coleta faz parte do registro.
    """
    titulo = models.CharField("Título", max_length=200)
    corpo_markdown = models.TextField("Conteúdo (Markdown)")
    periodo_inicio = models.DateField("Início do período analisado")
    periodo_fim = models.DateField("Fim do período analisado")
    dados_coletados_em = models.DateTimeField(
        "Dados coletados em",
        help_text="Momento do snapshot dos números usados na análise (vem no CSV exportado).")
    autor = models.ForeignKey("auth.User", null=True, blank=True,
                              on_delete=models.SET_NULL, verbose_name="Autor")
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Relatório de análise"
        verbose_name_plural = "Relatórios de análise"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.titulo} ({self.periodo_inicio:%d/%m}–{self.periodo_fim:%d/%m})"


class InstagramCollectionRun(models.Model):
    """Histórico de execuções do coletor."""
    STATUS = [
        ("executando", "Executando"),
        ("sucesso", "Sucesso"),
        ("parcial", "Concluída com erros"),
        ("erro", "Falhou"),
    ]
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="executando")
    escopo = models.CharField(max_length=200, blank=True)

    media_discovered = models.IntegerField(default=0)
    media_updated = models.IntegerField(default=0)
    snapshots_created = models.IntegerField(default=0)
    stories_snapshots = models.IntegerField(default=0)
    dias_atualizados = models.IntegerField(default=0)
    requests_made = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    error_summary = models.TextField(blank=True)

    class Meta:
        verbose_name = "Execução da coleta"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.started_at:%d/%m %H:%M} · {self.get_status_display()}"
