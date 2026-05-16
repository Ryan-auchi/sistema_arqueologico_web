from django.urls import path

from .views import api_sites, pesquisa_lista, pesquisa_mapa, site_detail

urlpatterns = [
    path("pesquisa/mapa/", pesquisa_mapa, name="pesquisa-mapa"),
    path("pesquisa/lista/", pesquisa_lista, name="pesquisa-lista"),
    path("pesquisa/sitio/<str:sitio_id>/", site_detail, name="pesquisa-detalhe"),
    path("api/sitios/", api_sites, name="api-sitios"),
]
