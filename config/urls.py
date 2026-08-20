from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("", include("analytics.urls")),
    path("painel/", include("painel.urls")),
    path("", include("imprensa.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static("/assets/", document_root=settings.BASE_DIR / "assets")
