from django.db import models
from django.utils import timezone


class Materia(models.Model):
    STATUS = [
        ("pendente", "Pendente de revisão"),
        ("aprovada", "Aprovada e publicada"),
        ("rejeitada", "Rejeitada"),
    ]
    jornalista = models.CharField("Nome do jornalista", max_length=120)
    veiculo = models.CharField("Veículo de imprensa", max_length=120)
    email = models.EmailField("E-mail para contato")
    telefone = models.CharField("Telefone (opcional)", max_length=40, blank=True)
    titulo = models.CharField("Título da matéria", max_length=200)
    texto = models.TextField("Texto da matéria")
    link = models.URLField("Link da publicação original (opcional)", blank=True)
    imagem = models.ImageField("Imagem (opcional)", upload_to="materias/%Y/%m/", blank=True)
    status = models.CharField("Status", max_length=12, choices=STATUS, default="pendente")
    criado_em = models.DateTimeField("Enviada em", auto_now_add=True)
    publicado_em = models.DateTimeField("Publicada em", null=True, blank=True)

    class Meta:
        verbose_name = "Matéria enviada"
        verbose_name_plural = "Matérias da imprensa"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.titulo} ({self.veiculo})"

    def aprovar(self):
        self.status = "aprovada"
        self.publicado_em = timezone.now()
        self.save(update_fields=["status", "publicado_em"])
