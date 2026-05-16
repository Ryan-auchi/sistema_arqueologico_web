<div align="center">

# Sistema Arqueológico — Web

**Painel de curadoria e consulta do ecossistema de dados arqueológicos**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app/)

</div>

---

## Visão Geral

Painel web do ecossistema arqueológico. Consome exclusivamente a **[sistema_arqueologico_api](https://github.com/mfeeee/sistema_arqueologico_api)** — não acessa banco de dados diretamente.

Oferece duas frentes de uso:

- **Pesquisa pública:** mapa interativo e listagem de sítios arqueológicos cadastrados
- **Curadoria:** fila de revisão de coletas enviadas pelo app mobile, aprovação ou rejeição de registros, seleção de campos a aplicar e histórico completo de auditoria por sítio

---

## Módulos

### Pesquisa
Mapa e listagem dos sítios publicados. Permite consulta por localização, tipo e natureza do bem. Os dados são consumidos em tempo real da API com cache local de 60 segundos.

### Curadoria
Fluxo de revisão técnica para curadores e administradores:
- Fila de coletas pendentes com filtro por status
- Tela de revisão comparando os dados da coleta com o sítio existente
- Seleção de campos individuais a aceitar ou rejeitar
- Controle de publicação do sítio no momento da aprovação

### Auditoria
Histórico completo de alterações por sítio. A tela de detalhe exibe uma comparação campo a campo entre o estado anterior e os valores aplicados, diferenciando campos alterados de campos de contexto.

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Django 5 · Python 3.12 |
| Arquivos estáticos | WhiteNoise |
| HTTP Client | Requests |
| Deploy | Railway (Docker) |
| CI | GitHub Actions (ruff + pytest) |

---

## Requisitos

- **Python** 3.12+
- **API** `sistema_arqueologico_api` rodando e acessível

---

## Instalação local

Existem duas formas de rodar o projeto localmente. **Docker** é o modo recomendado pois sobe a API e o painel juntos automaticamente.

---

### Opção A — Docker (recomendado)

Requer o repositório raiz `sistema_arqueologico` com ambos os projetos (`sistema_arqueologico_api` e `sistema_arqueologico_web`).

```bash
# na pasta raiz sistema_arqueologico/
docker compose up -d --build
```

O `entrypoint.sh` cuida automaticamente de `migrate` e `collectstatic` a cada inicialização. Nenhuma configuração adicional é necessária para desenvolvimento.

| Serviço | URL |
|---|---|
| Painel web (Django) | http://localhost:8000 |
| API (Laravel) | http://localhost:8001/api/v1 |

Para rodar seeders na API:

```bash
docker compose exec api_php php artisan db:seed
```

---

### Opção B — Python direto (sem Docker)

Requer a API (`sistema_arqueologico_api`) rodando separadamente na porta `8001`.

#### 1. Clone o repositório

```bash
git clone https://github.com/Ryan-auchi/sistema_arqueologico_web.git
cd sistema_arqueologico_web
```

#### 2. Crie e ative o ambiente virtual

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

#### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

#### 4. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com os valores do seu ambiente:

```dotenv
DEBUG=True
SECRET_KEY=sua-chave-secreta
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://localhost:8000
API_BASE_URL=http://127.0.0.1:8001/api/v1
API_TIMEOUT=15
```

#### 5. Execute as migrações

```bash
python manage.py migrate
```

#### 6. Inicie o servidor

```bash
python manage.py runserver
```

O painel estará disponível em **http://localhost:8000**.

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | ✅ | Chave secreta do Django |
| `DEBUG` | — | `True` em dev, `False` em produção |
| `ALLOWED_HOSTS` | ✅ | Hosts permitidos separados por vírgula |
| `CSRF_TRUSTED_ORIGINS` | ✅ em produção | Origens confiáveis para requisições POST |
| `API_BASE_URL` | ✅ | URL base da API (ex: `http://localhost:8001/api/v1`) |
| `API_TIMEOUT` | — | Timeout das requisições HTTP em segundos (padrão: 15) |

---

## Testes

```bash
# Instala dependências de desenvolvimento
pip install -r requirements-dev.txt

# Roda os testes
pytest --tb=short
```

### CI

A cada push ou pull request para `main`, o GitHub Actions executa automaticamente:

1. **Linter** — `ruff check .`
2. **Verificação de configuração** — `python manage.py check`
3. **Testes** — `pytest`

---

## Deploy (Railway)

O `Dockerfile` na raiz do projeto é detectado automaticamente pelo Railway. A cada push para `main` um novo deploy é disparado.

Variáveis obrigatórias no painel do Railway:

```
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=seu-dominio.up.railway.app
CSRF_TRUSTED_ORIGINS=https://seu-dominio.up.railway.app
API_BASE_URL=https://sistemaarqueologicoapi-production.up.railway.app/api/v1
```

---

## Perfis de Acesso

| Perfil | Acesso |
|---|---|
| `coletor` | Apenas pesquisa pública |
| `curador` | Pesquisa + fila de curadoria + auditoria |
| `admin` | Acesso total |

Os perfis são gerenciados pela API — o painel web reflete o perfil retornado no login.
