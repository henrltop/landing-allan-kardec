from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Painel · Professor Allan Kardec 20020"
admin.site.site_title = "Painel 20020"
admin.site.index_title = "Área da equipe de comunicação"

urlpatterns = [
    path("painel/", admin.site.urls),
    path("", include("imprensa.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
