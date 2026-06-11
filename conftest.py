"""
Fixtures e dados fake compartilhados por toda a suite de testes.
"""
import pytest

from pesquisa.models import Usuario

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures de usuário
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def curador_user(db):
    return Usuario.objects.create_user(
        email="curador@test.com",
        password="senha123",
        nome="Curador Teste",
        perfil=Usuario.PerfilUsuario.CURADOR,
    )


@pytest.fixture
def admin_user(db):
    return Usuario.objects.create_user(
        email="admin@test.com",
        password="senha123",
        nome="Admin Teste",
        perfil=Usuario.PerfilUsuario.ADMIN,
        is_staff=True,
    )


@pytest.fixture
def coletor_user(db):
    return Usuario.objects.create_user(
        email="coletor@test.com",
        password="senha123",
        nome="Coletor Teste",
        perfil=Usuario.PerfilUsuario.COLETOR,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dicts fake reutilizáveis
# ─────────────────────────────────────────────────────────────────────────────

SITE_FAKE = {
    "id": "abc-123",
    "nome_bem": "Sítio Pedra Furada",
    "codigo_iphan": "PI-0001",
    "natureza": "arqueologico",
    "tipo": "sitio",
    "uf": "PI",
    "municipio": "São Raimundo Nonato",
    "latitude": -8.48,
    "longitude": -42.60,
    "publicado": True,
    "geojson": None,
    "midias": [],
    "responsavel": {},
    "curador_responsavel": None,
    "nomes_populares": "",
    "meios_acesso": "",
    "artefatos": [],
    "descricao_atualizacao": "",
    "cep": "",
    "endereco": "",
    "ano_registro": 2020,
    "criado_em": None,
    "atualizado_em": None,
    "deletado_em": None,
}

# Coleta associada à curadoria (estrutura esperada por _incoming_data)
_COLETA_FAKE = {
    "id": "col-001",
    "nome_bem": "Sítio Novo",
    "codigo_iphan": "",
    "natureza_bem": "arqueologico",
    "tipo_bem": "sitio",
    "uf": "PI",
    "municipio": "São Raimundo Nonato",
    "latitude": -8.48,
    "longitude": -42.60,
    "artefatos": [],
    "dados_coletados": {
        "municipio": "São Raimundo Nonato",
        "cep": "",
        "endereco": "",
        "nomes_populares": "",
        "meios_acesso": "",
        "descricao_atualizacao": "",
    },
}

_USUARIO_FAKE = {"id": "user-001", "name": "Coletor Teste", "nome": "Coletor Teste"}

# Curadoria de coleta pendente (sem bem_material → criarSitio)
CURADORIA_COLETA_NOVA_FAKE = {
    "id": "cur-001",
    "status": "pendente",
    "entidade_tipo": "coleta",
    "entidade_id": "col-001",
    "bem_material_id": None,
    "acao_resultante": None,
    "observacao": "",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "usuario": _USUARIO_FAKE,
    "coleta": _COLETA_FAKE,
    "bem_material": {},
    "data_avaliacao": None,
}

# Curadoria de coleta pendente (com bem_material → atualizarSitio)
CURADORIA_COLETA_EXISTENTE_FAKE = {
    **CURADORIA_COLETA_NOVA_FAKE,
    "id": "cur-003",
    "bem_material_id": "abc-123",
    "bem_material": SITE_FAKE,
}

# Curadoria de artigo (novo artigo — artigo_id=None)
CURADORIA_ARTIGO_NOVO_FAKE = {
    "id": "cur-002",
    "status": "pendente",
    "entidade_tipo": "submissao_artigo",
    "entidade_id": "sub-001",
    "bem_material_id": "abc-123",
    "acao_resultante": None,
    "observacao": "",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "usuario": _USUARIO_FAKE,
    "bem_material": SITE_FAKE,
    "submissao_artigo": {
        "id": "sub-001",
        "titulo": "Artigo sobre Pedra Furada",
        "doi": "10.1000/xyz123",
        "autores": "Silva, João",
        "ano_publicacao": 2022,
        "periodico": "Revista Arqueológica",
        "idioma": "pt",
        "resumo": "Um estudo sobre sítios",
        "link_acesso": "https://example.com",
        "tipo_mencao": "citacao",
        "trecho_relevante": "Trecho relevante aqui",
        "artigo_id": None,
        "bem_material_id": "abc-123",
        "status": "pendente",
    },
}

# Curadoria de artigo com artigo já existente (artigo_id preenchido)
CURADORIA_ARTIGO_EXISTENTE_FAKE = {
    **CURADORIA_ARTIGO_NOVO_FAKE,
    "id": "cur-004",
    "submissao_artigo": {
        **CURADORIA_ARTIGO_NOVO_FAKE["submissao_artigo"],
        "artigo_id": "art-001",
    },
}

# Paginação fake para list_auditorias
PAGINACAO_VAZIA = {"total": 0, "page": 1, "pages": 1, "per_page": 50}

# Auditoria de inserção de BemMaterial (sem snap anterior)
AUDIT_INSERCAO_FAKE = {
    "id": "aud-001",
    "entidade_tipo": "App\\Models\\BemMaterial",
    "entidade_id": "abc-123",
    "curadoria_id": None,
    "operacao": "Inserção",
    "meio": "Curadoria",
    "data_hora": "2026-01-01T10:00:00Z",
    "created_at": "2026-01-01T10:00:00Z",
    "valor_anterior": None,
    "valor_novo": {"nome_bem": "Sítio Novo", "uf": "PI"},
    "usuario": {"id": "user-001", "name": "Curador Teste", "nome": "Curador Teste"},
    "curadoria": {},
}

# Auditoria de alteração de BemMaterial (tem snap anterior)
AUDIT_ALTERACAO_FAKE = {
    "id": "aud-002",
    "entidade_tipo": "App\\Models\\BemMaterial",
    "entidade_id": "abc-123",
    "curadoria_id": None,
    "operacao": "Alteração",
    "meio": "Curadoria",
    "data_hora": "2026-01-02T10:00:00Z",
    "created_at": "2026-01-02T10:00:00Z",
    "valor_anterior": {
        "nome_bem": "Sítio Antigo",
        "uf": "PI",
        "municipio": "Cidade Velha",
        "natureza": "arqueologico",
        "tipo": "sitio",
        "publicado": False,
        "artefatos": [],
        "latitude": -8.48,
        "longitude": -42.60,
    },
    "valor_novo": {"nome_bem": "Sítio Novo"},
    "usuario": {"id": "user-001", "name": "Curador Teste", "nome": "Curador Teste"},
    "curadoria": {},
}

# Auditoria de exclusão
AUDIT_EXCLUSAO_FAKE = {
    "id": "aud-003",
    "entidade_tipo": "App\\Models\\BemMaterial",
    "entidade_id": "abc-123",
    "curadoria_id": None,
    "operacao": "exclusao",
    "meio": "Manual",
    "data_hora": "2026-01-03T10:00:00Z",
    "created_at": "2026-01-03T10:00:00Z",
    "valor_anterior": {"nome_bem": "Sítio Deletado", "uf": "PI"},
    "valor_novo": None,
    "usuario": {"id": "user-001", "name": "Curador Teste", "nome": "Curador Teste"},
    "curadoria": {},
}

# Artigo com vinculos_count e vinculos
ARTIGO_FAKE = {
    "id": "art-001",
    "titulo": "Artigo sobre Pedra Furada",
    "doi": "10.1000/xyz123",
    "autores": "Silva, João",
    "ano_publicacao": 2022,
    "periodico": "Revista Arqueológica",
    "idioma": "pt",
    "resumo": "Um estudo arqueológico.",
    "link_acesso": "https://example.com",
    "verificado": True,
    "vinculos_count": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-06-01T00:00:00Z",
    "adicionado_por": {"id": "user-001", "name": "Curador Teste"},
    "vinculos": [
        {
            "id": "vin-001",
            "artigo_id": "art-001",
            "bem_material_id": "abc-123",
            "tipo_mencao": "citacao",
            "trecho_relevante": "Trecho importante.",
            "bem_material": {
                "id": "abc-123",
                "nome_bem": "Sítio Pedra Furada",
                "codigo_iphan": "PI-0001",
                "municipio": "São Raimundo Nonato",
                "uf": "PI",
            },
        }
    ],
}
