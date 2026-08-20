"""
Sincroniza o Instagram com o banco local.

Exemplos:
  python manage.py instagram_sync --since 2026-08-15
  python manage.py instagram_sync --since 2026-08-01 --until 2026-08-10
  python manage.py instagram_sync --max 50
  python manage.py instagram_sync --full          # backfill completo (paginação total)
  python manage.py instagram_sync --forcar        # ignora a estratégia de frequência
"""
from django.core.management.base import BaseCommand, CommandError

from analytics.sync import sincronizar


class Command(BaseCommand):
    help = "Coleta perfil, publicações e insights do Instagram (Meta Graph API)"

    def add_arguments(self, parser):
        parser.add_argument("--since", help="Data inicial (YYYY-MM-DD)")
        parser.add_argument("--until", help="Data final (YYYY-MM-DD)")
        parser.add_argument("--max", type=int, help="Máximo de mídias a processar")
        parser.add_argument("--full", action="store_true", help="Backfill completo, sem filtro de data")
        parser.add_argument("--forcar", action="store_true", help="Snapshot mesmo fora da janela de frequência")
        parser.add_argument("--auto", action="store_true",
                            help="Modo agendado: janela móvel dos últimos 14 dias (para o job de 1h)")

    def handle(self, *args, **opts):
        if opts["auto"]:
            from datetime import date, timedelta
            opts["since"] = (date.today() - timedelta(days=14)).isoformat()
        if opts["full"] and (opts["since"] or opts["until"]):
            raise CommandError("--full não combina com --since/--until")
        if not opts["full"] and not opts["since"] and not opts["max"]:
            raise CommandError("Informe --since, --max, --auto ou --full (proteção contra coleta acidental de 4 mil mídias)")

        escopo = "completo" if opts["full"] else f"since={opts['since']} until={opts['until']} max={opts['max']}"
        self.stdout.write(f"Iniciando coleta — escopo: {escopo}")

        run = sincronizar(since=opts["since"], until=opts["until"],
                          max_midias=opts["max"], forcar_snapshot=opts["forcar"])

        estilo = self.style.SUCCESS if run.status == "sucesso" else self.style.WARNING
        self.stdout.write(estilo(
            f"[{run.get_status_display()}] novas={run.media_discovered} "
            f"atualizadas={run.media_updated} snapshots={run.snapshots_created} "
            f"requests={run.requests_made} erros={run.errors_count}"
        ))
        if run.error_summary:
            self.stdout.write(run.error_summary[:2000])
