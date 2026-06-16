"""
Modelos locais do web_coletum.

O banco local existe exclusivamente para suportar a autenticação Django
(sessões, permissões). Todos os dados de sítios, coletas e curadorias
são lidos e escritos diretamente na API — não há espelho local.
"""

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models


class TimeStampedModel(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, nome, password=None, **extra_fields):
        if not email:
            raise ValueError("O email precisa ser informado.")
        if not nome:
            raise ValueError("O nome precisa ser informado.")

        email = self.normalize_email(email)
        extra_fields.setdefault("ativo", True)
        extra_fields.setdefault("is_staff", False)

        usuario = self.model(email=email, nome=nome, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, nome, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("ativo", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser precisa ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa ter is_superuser=True.")

        return self.create_user(email=email, nome=nome, password=password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Usuário local — espelha o perfil vindo da API após o login.

    Apenas email, nome e perfil são sincronizados; todos os dados de negócio
    (coletas, bens, curadorias) são exclusivos da API.
    """

    class PerfilUsuario(models.TextChoices):
        COLETOR = "coletor", "Coletor"
        CURADOR = "curador", "Curador"
        ADMIN = "admin", "Admin"

    class ClassificacaoUsuario(models.TextChoices):
        ESTUDANTE = "estudante", "Estudante"
        PROFESSOR = "professor", "Professor"
        ARQUEOLOGO = "arqueologo", "Arqueólogo"

    api_id = models.CharField(max_length=36, blank=True, default="")
    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    perfil = models.CharField(
        max_length=20,
        choices=PerfilUsuario.choices,
        default=PerfilUsuario.COLETOR,
    )
    classificacao = models.CharField(
        max_length=20,
        choices=ClassificacaoUsuario.choices,
        null=True,
        blank=True,
    )
    ativo = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ["nome"]

    def __str__(self) -> str:
        return f"{self.nome} <{self.email}>"

    @property
    def is_active(self) -> bool:
        return self.ativo
