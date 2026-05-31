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

Oferece três frentes de uso:

- **Pesquisa pública (guest):** mapa interativo e listagem de sítios arqueológicos acessíveis sem autenticação
- **Conta de usuário:** criação de conta e recuperação de senha integradas à API via modais no header
- **Curadoria:** fila de revisão de coletas e submissões de artigos científicos enviadas pelo app mobile, aprovação ou rejeição de registros, seleção de campos a aplicar e histórico completo de auditoria por sítio

---

## Módulos

### Pesquisa
Mapa e listagem dos sítios. Acessível sem autenticação (guest) — os endpoints da API usam `auth.optional:sanctum`, retornando dados públicos sem token. O token de sessão é aplicado por request nas views de pesquisa para evitar vazamento entre threads.

Os dados são consumidos em tempo real da API com cache local de 60 segundos. O controle de publicação na tela de detalhe do sítio (visível apenas para curador e admin) atualiza o registro via `PATCH /admin/bens-materiais/{id}/publicar`, registra auditoria e invalida o cache imediatamente.

**Filtros da listagem** — sidebar com os seguintes campos, todos aplicados localmente sobre o cache:

| Filtro | Campo pesquisado |
|---|---|
| Busca textual | `nome_bem`, `codigo_iphan`, `nomes_populares`, `municipio`, `descricao_atualizacao`, `artefatos` |
| Estado (UF) | `uf` — match exato |
| Município | `municipio` — match exato |
| Natureza | `natureza` — match exato |
| Tipo | `tipo` — match exato |
| Artefato | Filtra sítios que contêm o artefato selecionado na lista `artefatos` |
| Ano de Registro | Faixa de `ano_registro` (de / até) |
| Mostrar não publicados | Oculto por padrão; ao ativar exibe aviso de que os dados são preliminares |

A paginação preserva todos os filtros ativos nos links de navegação.

A tela de detalhe possui abas que expõem informações complementares do sítio:

| Aba | Visibilidade | Conteúdo |
|---|---|---|
| Sobre | Pública | Dados gerais, localização e mídias |
| Artigos | Pública | Artigos científicos vinculados ao sítio |
| Colaboradores | Usuário autenticado | Coletores e autores de artigos que contribuíram para o sítio |

A aba **Colaboradores** consome `GET /mobile/bens-materiais/{id}/colaboradores`. Retorna uma linha por usuário por tipo de contribuição — um mesmo usuário pode aparecer como "Coleta de campo" e "Artigo científico" se tiver contribuído nos dois fluxos. Se a API retornar erro, a mensagem é exibida na tela (com log `WARNING` no servidor) em vez de falhar silenciosamente.

**Ações administrativas** visíveis apenas para curador e admin (abaixo do controle de publicação):

- **Curador responsável** — exibe o responsável atual pelo sítio e oferece um seletor para alterá-lo. Qualquer curador ou admin pode trocar o responsável; a mudança é registrada em auditoria com os nomes dos envolvidos (não apenas UUIDs). O seletor é populado via `GET /admin/usuarios/curadores`.
- **Excluir bem material** — botão com confirmação JS que aciona `DELETE /admin/bens-materiais/{id}`. O registro é removido por soft delete (`deleted_at`) e a operação é registrada automaticamente como `exclusao` no log de auditoria.

### Autenticação
O header expõe um popover de login. Além do login padrão, há suporte a:

- **Criação de conta** — modal centralizado com campos nome, e-mail, senha e confirmação; chama `POST /api/v1/auth/register` e faz login automático
- **Recuperação de senha** — modal que chama `POST /api/v1/auth/password-reset`; não revela se o e-mail existe ou não

As notificações flash possuem auto-dismiss em 4 segundos e botão ✕ para fechar manualmente.

### Curadoria
Fluxo de revisão técnica para curadores e administradores. A fila é **polimórfica**: aceita tanto coletas de campo quanto submissões de artigos científicos enviadas pelo aplicativo móvel.

**Filtros da fila** — painel expansível ativado pelo botão "Filtros" na action bar:

| Filtro | Comportamento |
|---|---|
| Busca textual | Pesquisa em código IPHAN, nome, tipo de entrada e nome do usuário |
| Tipo de entrada | Coleta de campo ou Artigo científico |
| Destino da coleta | Novo sítio (sem `bem_material_id`) ou Sítio existente (com `bem_material_id`) |
| Conflitos | Com conflito / Sem conflito — baseado em diferenças reais de campo |
| Sou responsável | Filtra sítios onde o curador logado é o responsável |

O badge **"X conflitos"** no topo reflete o total de itens com conflito em toda a fila pendente, independentemente dos filtros ativos. O badge **"X filtrados"** aparece apenas quando o subconjunto visível difere do total.

**Detecção de conflito**: um item é marcado como conflito quando pelo menos um campo da coleta proposta difere do valor já existente no bem material oficial (campo com valor anterior não vazio). Campos preenchidos pela primeira vez não contam como conflito. A contagem aparece em cada linha da fila ("X campo(s) em conflito"). Novos sítios (sem bem_material) e artigos nunca têm conflito.

**Revisão de coleta** (`curadoria_revisao`):
- Comparação campo a campo entre a entrada recebida e o registro oficial
- Seleção de campos individuais a aceitar — respeitada tanto em `criarSitio` quanto em `atualizarSitio`
- Controle de publicação do sítio no momento da aprovação
- Ações: `criarSitio`, `atualizarSitio` ou rejeitar

**Revisão de artigo científico** (`curadoria_revisao_artigo`):
- Exibe metadados do artigo (DOI, autores, periódico, resumo, link de acesso)
- Indica se o artigo já existe na base (só criará o vínculo) ou se é novo (criará artigo + vínculo)
- Mostra o bem material vinculado e o tipo de menção
- Ações: aprovar vínculo (`aprovar_artigo`) ou rejeitar submissão

### Auditoria
Histórico completo de operações. A listagem (`audit_logs`) exibe labels específicos por tipo de entidade e operação:

| Operação registrada | Label exibido |
|---|---|
| Inserção de BemMaterial | INSERÇÃO |
| Alteração de BemMaterial | ALTERAÇÃO |
| Exclusão de BemMaterial | EXCLUSAO (badge vermelho) |
| Criação de vínculo artigo | VÍNCULO-ARTIGO |
| Remoção de vínculo artigo | REMOÇÃO-ARTIGO |
| Rejeição de curadoria | REJEIÇÃO |

**Filtros de auditoria** — painel expansível com os seguintes campos:

| Filtro | Comportamento |
|---|---|
| Busca textual | Pesquisa em usuário, operação, entidade, target e conteúdo dos snapshots |
| Tipo de operação | Seletor agrupado: sítios (todos, criação, alteração, exclusão, aprovação/rejeição de coleta) e artigos (vínculos, aprovação/rejeição) — filtra por `entidade_tipo` na API; operação específica aplicada localmente |
| Responsável pela ação | Busca textual no nome do usuário que realizou a ação |

**Tela de detalhe** (`audit_detail`):

- **Tabela de campos** — para auditorias vinculadas a uma curadoria, exibe os campos da coleta com status individual: `Aprovado` (verde), `Não aplicado` (cinza) ou `Rejeitado` (vermelho). Para auditorias manuais, mantém a comparação antes/depois tradicional.
- **Barra de resumo** — exibe o resultado da curadoria vinculada (aprovado/rejeitado) com badge colorido. O badge fica vermelho para operações de **Exclusão**.
- **Modal de snapshot** — exibe o estado anterior do registro em cards por seção. Para operações de **Alteração**, o botão "Ver mudanças" alterna para a visão do estado resultante com campos alterados destacados em azul. Para **Inserção**, o botão "Ver o que foi adicionado" revela os dados criados. Para **Rejeição**, exibe mensagem informando que nenhuma alteração foi feita. Para **Exclusão**, exibe banner vermelho "Registro excluído" com o último estado do sítio antes da deleção — o botão "Ver mudanças" não aparece neste caso.

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

| Perfil | Pesquisa pública | Aba Colaboradores | Fila de curadoria | Auditoria | Publicar / Excluir bem | Curador responsável |
|---|---|---|---|---|---|---|
| Guest (sem conta) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `coletor` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `curador` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `admin` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

Os perfis são gerenciados pela API — o painel web reflete o perfil retornado no login.
