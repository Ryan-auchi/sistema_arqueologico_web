from django.urls import path

from .views import auth_login, auth_logout, auth_recovery_placeholder, home

urlpatterns = [
    path("", home, name="home"),
    path("auth/login/", auth_login, name="auth-login"),
    path("auth/logout/", auth_logout, name="auth-logout"),
    path("auth/recovery/", auth_recovery_placeholder, name="auth-recovery"),
]
