from django.db import models

TEMAS = [
    ("educacao", "Educação"),
    ("ciencia", "Ciência e tecnologia"),
    ("qualificacao", "Qualificação e emprego"),
    ("esporte", "Esporte"),
    ("cultura", "Cultura"),
    ("juventude", "Juventude"),
    ("regional", "Desenvolvimento regional"),
]


class Lideranca(models.Model):
    nome = models.CharField("Nome", max_length=120)
    municipio = models.CharField("Município", max_length=80)
    funcao = models.CharField("Função / papel", max_length=120, blank=True,
                              help_text="Ex.: presidente de associação, diretor de escola, vereador…")
    telefone = models.CharField("Telefone / WhatsApp", max_length=40, blank=True)
    email = models.EmailField("E-mail", blank=True)
    observacoes = models.TextField("Observações", blank=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Liderança"
        verbose_name_plural = "Lideranças"
        ordering = ["municipio", "nome"]

    def __str__(self):
        return f"{self.nome} ({self.municipio})"


class Compromisso(models.Model):
    STATUS = [
        ("agendado", "Agendado"),
        ("confirmado", "Confirmado"),
        ("realizado", "Realizado"),
        ("cancelado", "Cancelado"),
    ]
    titulo = models.CharField("Título", max_length=160)
    inicio = models.DateTimeField("Data e hora")
    municipio = models.CharField("Município", max_length=80)
    local = models.CharField("Local", max_length=160, blank=True)
    descricao = models.TextField("Descrição", blank=True)
    responsavel = models.CharField("Responsável na equipe", max_length=80, blank=True)
    status = models.CharField("Status", max_length=12, choices=STATUS, default="agendado")

    class Meta:
        verbose_name = "Compromisso de agenda"
        verbose_name_plural = "Agenda interna"
        ordering = ["inicio"]

    def __str__(self):
        return f"{self.inicio:%d/%m %H:%M} · {self.titulo}"


class DemandaEscuta(models.Model):
    STATUS = [
        ("recebida", "Recebida"),
        ("analise", "Em análise"),
        ("respondida", "Respondida"),
    ]
    ORIGENS = [
        ("instagram", "Instagram"),
        ("presencial", "Presencial"),
        ("indicacao", "Indicação de liderança"),
        ("outro", "Outro"),
    ]
    tema = models.CharField("Tema", max_length=20, choices=TEMAS)
    municipio = models.CharField("Município", max_length=80)
    descricao = models.TextField("Descrição da demanda")
    origem = models.CharField("Origem", max_length=12, choices=ORIGENS, default="instagram")
    nome_contato = models.CharField("Nome de quem trouxe", max_length=120, blank=True)
    contato = models.CharField("Contato (telefone/rede)", max_length=120, blank=True)
    status = models.CharField("Status", max_length=12, choices=STATUS, default="recebida")
    resposta = models.TextField("Resposta / encaminhamento", blank=True)
    criado_em = models.DateTimeField("Registrada em", auto_now_add=True)

    class Meta:
        verbose_name = "Demanda da escuta"
        verbose_name_plural = "Demandas da escuta"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tema_display()} · {self.municipio}"
