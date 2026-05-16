# Web Coletum

Estrutura base de um projeto Django.

## Como usar

1. Crie e ative um ambiente virtual.
2. Instale as dependencias com `pip install -r requirements.txt`.
3. Copie `.env.example` para `.env` e ajuste os valores.
4. Configure a API em `http://127.0.0.1:8001` usando `API_BASE_URL` e, se a API exigir autenticação, defina `API_AUTH_TOKEN` no `.env`.
5. Execute `python manage.py migrate`.
6. Inicie o servidor com `python manage.py runserver`.

## Integração com a API

O projeto web deixa de ler os dados do banco local e passa a consultar a API Laravel exposta em `http://127.0.0.1:8001/api/v1`.

Variáveis esperadas no `.env`:

- `API_BASE_URL`: endereço base da API
- `API_AUTH_TOKEN`: token Bearer para rotas protegidas
- `API_TIMEOUT`: tempo limite das requisições HTTP em segundos
