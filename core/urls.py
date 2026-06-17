from django.urls import path

from .views import (
    auth_login,
    auth_logout,
    auth_password_reset,
    auth_password_reset_confirm,
    auth_register,
    excluir_conta,
    home,
    termos,
)

urlpatterns = [
    path("", home, name="home"),
    path("termos/", termos, name="termos"),
    path("auth/login/", auth_login, name="auth-login"),
    path("auth/logout/", auth_logout, name="auth-logout"),
    path("auth/register/", auth_register, name="auth-register"),
    path("auth/password-reset/", auth_password_reset, name="auth-password-reset"),
    path("auth/redefinir-senha/", auth_password_reset_confirm, name="auth-password-reset-confirm"),
    path("auth/conta/excluir/", excluir_conta, name="excluir-conta"),
]
