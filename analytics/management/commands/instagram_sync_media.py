"""
Sincroniza UMA mídia específica (modo teste/validação).

Exemplo:
  python manage.py instagram_sync_media 18631351960043833
"""
from django.core.management.base import BaseCommand

from analytics.models import InstagramMedia
from analytics.normalize import metricas_derivadas
from analytics.sync import sincronizar


class Command(BaseCommand):
    help = "Coleta metadados e insights de uma única mídia do Instagram"

    def add_arguments(self, parser):
        parser.add_argument("media_id")

    def handle(self, *args, **opts):
        run = sincronizar(apenas_media_id=opts["media_id"], forcar_snapshot=True)
        if run.status == "erro":
            self.stderr.write(self.style.ERROR(run.error_summary))
            return
        media = InstagramMedia.objects.filter(instagram_media_id=opts["media_id"]).first()
        snap = media.ultimo_snapshot if media else None
        self.stdout.write(self.style.SUCCESS(f"OK — snapshots criados: {run.snapshots_created}"))
        if snap:
            base = {c: getattr(snap, c) for c in
                    ["views", "reach", "likes", "comments", "saved", "shares",
                     "reposts", "total_interactions", "total_watch_time_ms",
                     "avg_watch_time_ms", "reels_skip_rate"]}
            self.stdout.write(f"normalizado: {base}")
            self.stdout.write(f"derivadas:   {metricas_derivadas(snap)}")
