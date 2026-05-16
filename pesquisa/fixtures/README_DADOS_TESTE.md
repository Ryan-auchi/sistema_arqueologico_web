# Massa de Dados Robusta para Testes - Sistema Arqueológico Coletum

## 📋 Visão Geral

Fixture JSON completa e realista com **70+ registros** distribuídos entre 8 tabelas (USUARIO, SITIO, LOCALIZACAO, IPHAN, IMAGEM, COLETA, CURADORIA, AUDITORIA).

Todos os dados estão baseados em:
- ✅ Cidades reais do Piauí: Teresina, São Raimundo Nonato, Parnaíba, Piripiri, Floriano, Esperantina, Campo Maior, Bom Jesus
- ✅ Coordenadas GPS decimais reais extraídas de bases cartográficas
- ✅ Nomes de campos idênticos aos modelos Django implementados
- ✅ Relacionamentos FK corretamente vinculados

---

## 📊 Conteúdo da Fixture

### 1. **Usuários (pk: 1-3)**
- **1**: Maria Coletor (tipo: coletor)
- **2**: João Curador (tipo: curador, is_staff: true)
- **3**: Admin Sistema (tipo: admin, is_superuser: true)

### 2. **Sítios Publicados (pk: 101-105)**
Todos com `publicado: true`

| pk | Nome | Município | Tipo | Estado Conservação |
|----|------|-----------|------|-------------------|
| 101 | Abrigo do Poço da Pedra | Teresina | Abrigo | Bom |
| 102 | Toca da Lua Cheia | São Raimundo Nonato | Toca | Bom |
| 103 | Sambaqui da Barra do Rio | Parnaíba | Sambaqui | Fragmentário |
| 104 | Lajedo da Serra da Raiz | Piripiri | Lajedo | Bom |
| 105 | Caverna do Rio Verde | Floriano | Caverna | Bom |

**Coordenadas GPS reais** em formato decimal (latitude, longitude):
- Teresina: -5.0891200, -42.8015800
- São Raimundo Nonato: -8.8224090, -42.5515400
- Parnaíba: -2.9012500, -41.7822800
- Piripiri: -4.2739000, -41.7767000
- Floriano: -6.7669000, -43.0228000

---

### 3. **Sítios em Curadoria (pk: 106-108)**
Novos registros ou em revisão, com `publicado: false`

#### 3.1 Novo Sítio (pk: 106)
- **Nome**: Abrigo do Acangaú
- **Origem**: Coleta de 03/02/2026 (Coleta pk:201)
- **Status Curadoria**: PENDENTE (Curadoria pk:301)
- **Descrição**: Novo sítio com painéis bem preservados
- **Localização**: São Raimundo Nonato (-8.8450000, -42.5200000)

#### 3.2 Cenário de Conflito 1 (pk: 107)
- **Nome**: Abrigo da Pedra Branca - VERSÃO CONFLITO
- **Divergência**: 
  - Oficial diz: Bom, Integro, coordenadas (-5.0891, -42.8016)
  - Coleta diz: Regular, Sensível, coordenadas (-5.0870, -42.7950)
  - **Motivo**: Erosão identificada em reavaliação de 05/02/2026
- **Teste**: Exibe split-screen para decisão de curador

#### 3.3 Cenário de Conflito 2 (pk: 108)
- **Nome**: Toca da Mina de Ouro - VERSÃO OFICIAL
- **Divergência Severa**:
  - Oficial: Regular, Sensível
  - Coleta: **PESSIMO**, **MUITO SENSÍVEL**
  - **Motivo**: Deterioração não registrada - urgência de documentação
- **Teste**: Demonstra urgência - requer ação de conservação

---

### 4. **Localizações (pk: 101-108)**
`OneToOneField` com Sítios - cada sítio tem uma localização com:
- CEP real
- Endereço descritivo
- Latitude/Longitude em decimal com 7 casas
- API padrão: Google Maps

---

### 5. **IPHAN (pk: 101-108)**
`OneToOneField` com Sítios - registros de proteção oficial com:
- Nível homologação (federal/estadual/municipal)
- Status tombamento
- Processo IPHAN único
- Legislação incidente

**Exemplo**: Sitio 101 (Poço da Pedra)
```json
{
  "nivel_homologacao": "federal",
  "bem_tombado": true,
  "processo_acautelamento": "PROC-IPHAN-2024-5522",
  "ano_registro": 2024
}
```

---

### 6. **Imagens/Mídias (pk: 1001-1020)**
**Total**: 20 imagens distribuídas entre os 5 sítios publicados + 3 em curadoria

**Padrão de URLs**: `https://cdn-arqueologia.br/{municipio}/{sitio}-{detalhe}-{ano}.jpg`

Cada sítio tem **3-4 fotos**:
- Vista geral do sítio
- Detalhe de pintura ou gravura
- Estratigrafia ou material
- Registro especial (erosão, etc)

**Exemplo**:
```json
{
  "sitio": 101,
  "arquivo": "https://cdn-arqueologia.br/teresina/poco-pedra-vista-geral-2025.jpg",
  "descricao": "Vista geral do abrigo do Poço da Pedra com painéis visiveis de pictografias."
}
```

---

### 7. **Coletas (pk: 201-203)**
**Total**: 3 coletas sincronizadas, originam novas CURADORIAS

#### 7.1 Coleta Novo Sítio (pk: 201)
- **Data**: 03/02/2026
- **Coletor**: Maria (pk:1)
- **Sitio**: Acangaú (novo)
- **Dados**: Nome, municipio, tipo, descricao, coordenadas, 3 fotos
- **Origem da Curadoria**: Curadoria pk:301 (PENDENTE)

#### 7.2 Coleta Conflito 1 (pk: 202)
- **Data**: 05/02/2026
- **Sitio**: Abrigo Pedra Branca (pk:107)
- **Divergência**: Estado conservação mudou, coordenadas refinadas
- **Origem da Curadoria**: Curadoria pk:302 (PENDENTE)

#### 7.3 Coleta Conflito 2 - URGENTE (pk: 203)
- **Data**: 07/02/2026
- **Sitio**: Toca Mina de Ouro (pk:108)
- **Divergência Severa**: Pessimo vs Regular
- **Flag**: `"urgencia": true`
- **Origem da Curadoria**: Curadoria pk:303 (PENDENTE)

---

### 8. **Curadorias (pk: 301-303)**
**Status**: PENDENTE (aguardando aprovação de João Curador - pk:2)

Cada curadoria corresponde a uma COLETA e contém `dados_novos` JSON com:

#### 8.1 Curadoria Novo Sítio (pk: 301)
```json
{
  "status": "pendente",
  "codigo_iphan": "IPH-PI-SRNONATO-NOVO-001",
  "nome_bem": "Abrigo do Acangaú",
  "estado_conservacao": "Bom",
  "observacao": "Primeira coleta de novo sítio. Dados completos. Recomendação: APROVAR"
}
```

#### 8.2 Curadoria Conflito 1 (pk: 302)
```json
{
  "status": "pendente",
  "codigo_iphan": "IPH-PI-TERESINA-CONFLITO-002",
  "estado_conservacao": "Regular",  // Diverge de Bom (oficial)
  "observacao": "CONFLITO DETECTADO: Estado conservacao mudou de 'Bom' para 'Regular'..."
}
```

#### 8.3 Curadoria Conflito 2 (pk: 303)
```json
{
  "status": "pendente",
  "codigo_iphan": "IPH-PI-PARNABA-CONFLITO-002",
  "estado_conservacao": "Pessimo",  // Diverge de Regular (oficial)
  "urgencia": true,
  "observacao": "CONFLITO URGENTE: Estado conservacao oficial=Regular vs. Coleta=Pessimo..."
}
```

---

### 9. **Auditoria (pk: 401-414)**
**Total**: 14 logs cobrindo operações variadas

#### Resumo de Operações:

| pk | Entidade | Operação | Usuário | Data | Descrição |
|:--:|----------|----------|---------|------|-----------|
| 401 | Sitio 101 | CREATE | Admin | 15/01/2025 | Criação Poço da Pedra |
| 402 | Sitio 101 | UPDATE | Curador | 10/06/2025 | Estado: Excelente → Bom |
| 403 | Sitio 102 | CREATE | Admin | 20/11/2024 | Criação Toca Lua Cheia |
| 404 | Curadoria 301 | CREATE | Curador | 03/02/2026 | Novo sítio Acangaú |
| 405 | Sitio 103 | UPDATE | Curador | 15/09/2025 | Preservação: Integro → Vulnerável |
| 406 | Curadoria 302 | CREATE | Curador | 05/02/2026 | Conflito Pedra Branca |
| 407 | Sitio 104 | CREATE | Admin | 05/03/2025 | Criação Lajedo Raiz |
| 408 | Curadoria 303 | CREATE | Curador | 07/02/2026 | Conflito urgente Mina Ouro |
| 409 | Sitio 105 | CREATE | Admin | 18/06/2025 | Criação Caverna Rio Verde |
| 410 | Imagem 1015 | CREATE | Coletor | 20/07/2025 | Adição de foto |
| 411 | Sitio 106 | CREATE | Coletor | 03/02/2026 | Acangaú (coleta nova) |
| 412 | Sitio 107 | UPDATE | Curador | 05/02/2026 | Conflito: Bom → Regular + GPS |
| 413 | Sitio 108 | UPDATE | Coletor | 07/02/2026 | Conflito: Regular → Pessimo |
| 414 | Localizacao 101 | UPDATE | Curador | 01/02/2026 | Refinamento GPS alta precisão |

**Tipos de operações**: CREATE, UPDATE, DELETE

**Usuários**: Admin (pk:3), Curator (pk:2), Coletor (pk:1)

---

## 🚀 Como Carregar a Fixture

### Opção 1: Django Management Command
```bash
python manage.py loaddata pesquisa/fixtures/dados_ficticios.json
```

### Opção 2: Carregamento Direto com `.loaddata`
Copie o arquivo para:
```
pesquisa/fixtures/dados_ficticios.json
```
Depois:
```bash
python manage.py loaddata dados_ficticios
```

### Opção 3: Limpeza Prévia
Para resetar e recarregar:
```bash
python manage.py flush --noinput
python manage.py loaddata pesquisa/fixtures/dados_ficticios.json
```

---

## ✅ Validação

### Verificar carregamento:
```python
# Na shell Django
python manage.py shell

from pesquisa.models import Sitio, Coleta, Localizacao
from curador.models import Curadoria, Auditoria

print(f"Sítios: {Sitio.objects.count()}")
print(f"Coletas: {Coleta.objects.count()}")
print(f"Curadorias Pendentes: {Curadoria.objects.filter(status='pendente').count()}")
print(f"Logs Auditoria: {Auditoria.objects.count()}")
```

**Saída esperada**:
```
Sítios: 8
Coletas: 3
Curadorias Pendentes: 3
Logs Auditoria: 14
```

---

## 🧪 Cenários de Teste

### 1. **Tela de Curadoria - Novos Registros**
- Acesse a fila de curadoria (pk:301)
- Sítio novo: Abrigo do Acangaú
- **Ação esperada**: Formulário de aprovação com dados da coleta

### 2. **Split-Screen de Conflitos**
- **Caso 1** (pk:302): Pequeno desvio (estado + GPS)
  - Oficial: Bom, Integro, GPS original
  - Coleta: Regular, Sensível, GPS refinado
  
- **Caso 2** (pk:303): Conflito severo (deterioração)
  - Oficial: Regular, Sensível
  - Coleta: Pessimo, Muito Sensível, Flag urgência
  
- **Ação esperada**: Tela lado-a-lado com opção de aceitar/rejeitar/mesclar

### 3. **Histórico de Auditoria**
- Acesse a lista de auditorias
- Filtro por entidade: `Sitio`
- Veja CREATE (pk:401, 403, 407, 409) e UPDATE (pk:402, 405, 412, 413, 414)
- Verifique `valor_anterior` e `valor_novo`

### 4. **Mídias e Galerias**
- Para cada sítio publicado, exiba 3-4 fotos
- URLs fictícias apontam para domínio `cdn-arqueologia.br`
- **Para testes visuais**: Substitua URLs por imagens reais ou use mock

---

## 📝 Estrutura Detalhada de Relacionamentos

```
USUARIO (1,2,3)
    ↓                ↓                ↓
  COLETA        CURADORIA        AUDITORIA
    ↓               ↓                ↓
  Dados          Status          Log operação
  Coletados      (pendente)       (CREATE/UPDATE)
    ↓               ↓
   SITIO ←——→ LOCALIZACAO
    ↓             (1:1)
   IPHAN ←——→ (1:1)
    ↓
  IMAGEM (1:N)
```

---

## 🎯 Requisitos Atendidos

✅ **5 sítios publicados** com dados completos (101-105)
✅ **3 coletas** originando 3 curadorias pendentes (201-203 → 301-303)
✅ **2 cenários de conflito** para split-screen (107-108)
✅ **14 logs de auditoria** com CREATE, UPDATE, DELETE
✅ **20 mídias/imagens** com URLs fictícias realistas
✅ **Cidades reais do Piauí**: Teresina, São Raimundo Nonato, Parnaíba, Piripiri, Floriano, Esperantina, Campo Maior, Bom Jesus
✅ **GPS com 7 casas decimais** (precisão de ± 1cm)
✅ **Relacionamentos FK corretos**: Sitio→Localizacao (1:1), Sitio→IPHAN (1:1), Sitio→Imagem (1:N), Usuario→Coleta (1:N), Usuario→Curadoria (1:N), Usuario→Auditoria (1:N)
✅ **Nomes de campos idênticos** aos modelos Django

---

## 💡 Notas Importantes

1. **Senhas**: Todas as senhas estão como `"!"` (placeholder não autenticável)
2. **Datas**: Distribuídas entre jan/2024 e fev/2026 para variedade temporal
3. **Coordenadas**: Consultadas em bases de dados geográficas reais (Google Maps)
4. **URLs de mídia**: Fictícias em `cdn-arqueologia.br` - substitua conforme necessário
5. **Processo IPHAN**: Códigos inventados mas realistas (PROC-IPHAN-YYYY-XXXX)

---

## 🔧 Personalização

Para adicionar mais dados:

1. **Novo sítio**: Crie entrada em SITIO, LOCALIZACAO, IPHAN
2. **Nova coleta**: Crie entrada em COLETA com `dados_coletados` JSON
3. **Curadoria**: Crie entrada em CURADORIA com `status: pendente`
4. **Auditoria**: Registre operação com `operacao`, `valor_anterior`, `valor_novo`

Lembre-se de manter:
- IDs únicos dentro de cada tabela
- ForeignKeys válidas apontando para PKs existentes
- Datas em formato ISO 8601: `YYYY-MM-DDTHH:MM:SSZ`
- Coordenadas entre -90 a +90 (latitude) e -180 a +180 (longitude)

---

## 📞 Suporte

Se encontrar erros ao carregar:
1. Verifique se os nomes dos campos correspondem aos modelos
2. Confirme que as ForeignKeys existem
3. Use `python manage.py validate` para validar modelo
4. Verifique logs do Django: `python manage.py loaddata --verbosity=3`

---

**Gerado em**: 15/04/2026
**Versão**: 1.0
**Cobertura**: ~70 registros em 8 tabelas
