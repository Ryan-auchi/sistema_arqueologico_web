from django.contrib import admin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    """
    Admin somente-leitura. Usuários são criados e gerenciados exclusivamente
    via login na API — edição manual aqui desincronizaria os dados.
    """

    list_display = ("nome", "email", "perfil", "classificacao", "ativo", "is_staff")
    search_fields = ("nome", "email")
    list_filter = ("perfil", "classificacao", "ativo", "is_staff")
    readonly_fields = ("nome", "email", "perfil", "classificacao", "ativo", "is_staff", "last_login")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
