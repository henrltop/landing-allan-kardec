from django.conf import settings
from django.http import FileResponse


def landing(request):
    """Serve a landing estática na raiz (em produção o nginx faz isso direto)."""
    return FileResponse(open(settings.BASE_DIR / "index.html", "rb"), content_type="text/html")
