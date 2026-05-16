from django.contrib import admin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "perfil", "classificacao", "ativo", "is_staff")
    search_fields = ("nome", "email")
    list_filter = ("perfil", "classificacao", "ativo", "is_staff")
