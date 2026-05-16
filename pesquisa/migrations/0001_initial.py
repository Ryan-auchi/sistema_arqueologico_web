from django.db import migrations, models

import pesquisa.models


class Migration(migrations.Migration):
    """
    Migration inicial do app pesquisa.

    Cria apenas a tabela de Usuario local, usada exclusivamente para
    autenticação Django (sessões, permissões). Todos os dados de negócio
    (coletas, bens, curadorias, auditorias) são gerenciados pela API Laravel.
    """

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Usuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("nome", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254, unique=True)),
                (
                    "perfil",
                    models.CharField(
                        choices=[("coletor", "Coletor"), ("curador", "Curador"), ("admin", "Admin")],
                        default="coletor",
                        max_length=20,
                    ),
                ),
                (
                    "classificacao",
                    models.CharField(
                        blank=True,
                        choices=[("estudante", "Estudante"), ("professor", "Professor"), ("arqueologo", "Arqueólogo")],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("is_staff", models.BooleanField(default=False)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "Usuário",
                "verbose_name_plural": "Usuários",
                "ordering": ["nome"],
            },
            managers=[
                ("objects", pesquisa.models.UsuarioManager()),
            ],
        ),
    ]
