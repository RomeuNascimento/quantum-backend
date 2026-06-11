# Quantum Backend — CLAUDE.md

## Estado do Projeto

**Criado em:** 2026-05-20
**Última sessão:** 2026-06-11 (tarde — branch `claude/keen-ptolemy-mmed2k`, continua a `claude/sharp-noether-6ml8uh`)
**Próxima sessão:** Fase 2 restante (snapshot de custo / refactor cálculo) ou Fase 1 restante (M1/M5–M8)
**Status:** PRODUÇÃO — backend rodando em api.quantumcalc.com.br

---

## O que foi feito

- [x] Estrutura completa do projeto criada
- [x] Models SQLAlchemy (todos os módulos)
- [x] Auth JWT (register, login, /me)
- [x] Routers: ingredientes, embalagens, receitas, produtos, precificacao, custos_fixos
- [x] Schemas Pydantic por módulo
- [x] Migrations com Alembic
- [x] Dockerfile
- [x] requirements.txt
- [x] .env.example
- [x] Push inicial para GitHub
- [x] **Receita `tipo` → texto livre** (2026-05-20)
  - Removido `TipoReceitaEnum` do `models.py`
  - `tipo = Column(String(100), nullable=True)` (era `Enum`, `nullable=False`)
  - Schemas atualizados: `tipo: Optional[str] = None` em todos os schemas de receita
  - Migration `002_receita_tipo_livre.py` rodada em produção (PostgreSQL ENUM → VARCHAR(100))
- [x] **Produtos — seção unificada "Preparações"** (2026-05-20)
  - `schemas/produtos.py`: `ProdutoMassaCreate` + `ProdutoRecheioCreate` → `ProdutoPreparacaoCreate`; campos `massas`/`recheios` → `preparacoes`
  - `routers/produtos.py`: leitura une `produto.massas + produto.recheios` em `preparacoes`; escrita salva tudo em `ProdutoMassa`; update deleta ambas as tabelas antes de recriar
  - Sem migration — tabela `produto_recheios` existe e fica vazia para novos produtos (não dropar)
- [x] **Importação via IA** (2026-05-20)
  - `requirements.txt`: adicionado `anthropic>=0.40.0`
  - Novo router `app/routers/ia.py` com dois endpoints:
    - `POST /ia/nota-fiscal` — recebe imagem/PDF, extrai itens via Claude e retorna JSON
    - `POST /ia/receitas` — recebe imagem/PDF/texto/Excel, extrai receitas via Claude e retorna JSON
  - `app/main.py`: registrado `ia_router`
  - Env vars necessárias: `ANTHROPIC_API_KEY` (obrigatório), `ANTHROPIC_MODEL` (padrão: `claude-opus-4-5`)
- [x] **ANTHROPIC_API_KEY configurada no EasyPanel** (2026-05-21)
  - IA ativa em produção
- [x] **Campo `marca` em Ingrediente** (2026-05-21)
  - `models.py`: `marca = Column(String(100), nullable=True)` adicionado a `Ingrediente`
  - `schemas/ingredientes.py`: `marca: Optional[str] = None` em `IngredienteCreate`, `IngredienteUpdate`, `IngredienteOut`
  - `routers/ingredientes.py`: `marca=dados.marca` passado na criação
  - Migration `003_ingrediente_marca.py` rodada em produção
- [x] **Prompt IA nota fiscal normaliza nomes** (2026-05-21)
  - `PROMPT_NOTA` atualizado: extrai `nome` genérico (ex: "Achocolatado") + `marca` separados
  - Antes retornava o código fiscal bruto (ex: "ACHOC. NESTLE S/A 120G")
  - Resolve o problema de ingredientes duplicados entre nota fiscal e importação de receitas

---

## Stack

- **Framework:** FastAPI (Python 3.11)
- **ORM:** SQLAlchemy 2.x + Alembic (migrations)
- **Auth:** JWT (python-jose + passlib bcrypt)
- **Banco:** PostgreSQL (psycopg2)
- **IA:** Anthropic Claude API (`anthropic>=0.40.0`)
- **Deploy:** EasyPanel → https://api.quantumcalc.com.br

---

## Variáveis de Ambiente (EasyPanel)

```
DATABASE_URL=postgresql+psycopg2://postgres:<SENHA>@quantum_quantum-db:5432/quantum
JWT_SECRET=<ver no EasyPanel — gerado com secrets.token_hex(32)>
JWT_ALGORITHM=HS256
JWT_EXPIRATION=30
ALLOW_ORIGINS=https://quantumcalc.com.br

# IA (obrigatório para /ia/* endpoints)
ANTHROPIC_API_KEY=<configurada no EasyPanel — ativa>
ANTHROPIC_MODEL=claude-opus-4-5   # opcional, este é o padrão

# Banco externo (para rodar alembic do local):
# postgresql://postgres:<SENHA>@72.61.132.202:5432/quantum
```

> **Atenção:** sem `ANTHROPIC_API_KEY` configurada, os endpoints `/ia/nota-fiscal` e `/ia/receitas` retornam HTTP 503.

---

## Arquitetura

```
app/
├── main.py          — FastAPI app, CORS, routers registrados
├── database.py      — Engine SQLAlchemy, SessionLocal, Base
├── auth/
│   ├── router.py    — POST /auth/register, /auth/login, GET /auth/me
│   ├── schemas.py   — UserCreate, UserLogin, Token, UserOut
│   └── utils.py     — hash/verify password, create/decode JWT
├── models/
│   └── models.py    — Todos os modelos SQLAlchemy
├── routers/
│   ├── ingredientes.py   — CRUD + histórico de preços
│   ├── embalagens.py     — CRUD + histórico de preços
│   ├── receitas.py       — CRUD + cálculo custo (MP + MO)
│   ├── produtos.py       — CRUD + cálculo custo composto (unifica massas+recheios em preparacoes)
│   ├── precificacao.py   — Canais + preços sugeridos
│   ├── custos_fixos.py   — CRUD custos fixos
│   └── ia.py             — POST /ia/nota-fiscal, POST /ia/receitas (Anthropic Claude)
└── schemas/
    └── (um arquivo por módulo)

migrations/
└── versions/
    ├── 001_initial.py
    ├── 002_receita_tipo_livre.py   — ENUM → VARCHAR(100), nullable=True
    └── 003_ingrediente_marca.py    — ADD COLUMN marca VARCHAR(100) nullable
```

---

## Regras de negócio críticas

1. **Multi-tenant:** Todo SELECT filtra por `user_id` do token JWT
2. **Custo unitário ingrediente:** `(preco / (qtd_embalagem × fator_unidade)) / fator_correcao` — registro mais recente; `fator_unidade` = 1000 para kg/L, 1 para g/ml/unid (consumo é sempre em g/ml)
3. **Custo unitário embalagem:** `preco / qtd_embalagem` — registro mais recente
4. **Custos de receita:** Calculados na API, nunca persistidos
5. **Custo proporcional produto:** `fator = qtd_usada / rendimento_g` → aplica sobre custo_mp e custo_mo da receita
6. **Preço sugerido:** `custo_total / (1 - margem - taxa_plataforma - taxa_cartao - imposto)`
7. **Soft delete:** Ingrediente/embalagem usados em receita → apenas `ativo=False`, não deleta
8. **Canal iFood** pré-cadastrado na criação de conta (taxa_plataforma=12%, taxa_cartao=2.99%, imposto=6%)
9. **Preparações de produto:** leitura une `produto.massas + produto.recheios`; escrita sempre em `ProdutoMassa`
10. **Ingrediente.marca:** campo opcional — exibido como `Nome · Marca`; matching de receita usa só `nome`

---

## Bugs conhecidos / Armadilhas

### Produtos — tabelas massas/recheios no banco
O banco tem `produto_massas` e `produto_recheios`. A leitura une as duas em `preparacoes`. A escrita salva tudo em `produto_massas`. A tabela `produto_recheios` existe mas fica vazia para novos produtos — **não dropar por ora** (dados antigos ainda existem).

### IA — dependência de ANTHROPIC_API_KEY
Os endpoints `/ia/nota-fiscal` e `/ia/receitas` retornam HTTP 503 se `ANTHROPIC_API_KEY` não estiver configurada no EasyPanel (serviço `backend`). O modelo padrão é `claude-opus-4-5` (substituível via `ANTHROPIC_MODEL`).

### IA — parse de resposta
O Claude às vezes envolve o JSON em blocos de código markdown (` ```json ... ``` `). O helper `_parse()` em `ia.py` tira essa formatação antes do `json.loads()`. Se o JSON vier malformado, o endpoint retorna HTTP 422.

### Migration 002 — ENUM PostgreSQL
A migration converte o ENUM nativo do PostgreSQL para VARCHAR(100). O downgrade recria o ENUM e faz UPDATE/cast — cuidado ao rodar downgrade em produção se houver valores fora de `('massa', 'recheio')` na coluna.

### bcrypt
Fixado em `4.0.1` para compatibilidade com passlib 1.7.4. Não atualizar sem testar.

### "Erro ao conectar com o servidor" no frontend
Mensagem genérica do `client.js` quando `error.response` é `undefined` (sem resposta HTTP). Causa mais comum: backend reiniciando após deploy. Aguardar o serviço subir e tentar novamente.

---

## Deploy EasyPanel

- **Build type:** nixpacks
- **buildCommand:** `pip install -r requirements.txt`
- **startCommand:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Domínio:** `api.quantumcalc.com.br` porta 8000, HTTPS true
- **autoDeploy:** false (deploy manual via painel ou API)

> **Migrations:** rodar manualmente do local com todas as env vars:
> `DATABASE_URL=postgresql+psycopg2://...@72.61.132.202:5432/quantum JWT_SECRET=... alembic upgrade head`
> O banco externo fica em `72.61.132.202:5432` (porta 5432 exposta no EasyPanel).
>
> ⚠️ **PENDENTE: rodar `alembic upgrade head` em produção** — a migration 004
> (índices + UNIQUE produto_precos com dedupe) foi criada em 2026-06-11 e ainda
> não foi aplicada no banco de produção.

### Deploy manual via API
```bash
curl -X POST https://panel.quantumcalc.com.br/api/trpc/services.app.deployService \
  -H "Authorization: Bearer <EASYPANEL_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"json":{"projectName":"quantum","serviceName":"backend"}}'
```

---

## Auditoria 2026-06-11 — Revisão completa (backend)

> Revisão de código completa feita em 2026-06-11. Itens abaixo ordenados por prioridade.
> Roadmap de funcionalidades novas: ver seção "Roadmap de funcionalidades" no CLAUDE.md do **frontend**.

### 🔴 Críticos (Fase 0) — ✅ TODOS CORRIGIDOS em 2026-06-11 (commit na branch claude/sharp-noether-6ml8uh)

- [x] **C1. IDOR em Produtos (criar/atualizar)** — `routers/produtos.py:129-136` e `:188-204`: IDs aninhados (`receita_id`, `ingrediente_id`, `embalagem_id`) NÃO são validados contra `user_id`. Usuário autenticado vincula entidades de outro tenant e o GET seguinte vaza nome/quantidades/custos. Fix: validar todo ID aninhado com filtro `user_id == user.id` (helper `get_owned_or_404`).
- [x] **C2. IDOR em Receitas (atualizar)** — `routers/receitas.py:174-193`: `PUT /receitas/{id}` recria `ReceitaIngrediente` sem validar ownership do `ingrediente_id` (o POST valida, o PUT não). Idem `colaborador_id` nas `etapas_mo` (create E update).
- [x] **C3. IA bloqueante** — `routers/ia.py:110-114, 144`: cliente `anthropic.Anthropic` SÍNCRONO dentro de `async def` → trava o event loop inteiro por 30–90s durante processamento (login e tudo mais param). Fix: `AsyncAnthropic` + `await`, ou trocar endpoint para `def` síncrono (threadpool).
- [x] **C4. Upload sem limite + sem rate limiting em /ia/** — `ia.py:107, 132`: `await file.read()` sem limite de tamanho (OOM/DoS) e sem rate limiting — registro de conta é aberto, qualquer um pode queimar créditos Anthropic em loop. Fix: limite ~15MB + rate limit por usuário.
- [x] **C5. Exception handler global sem log** — `main.py:32-37`: 500 mudo, sem `logger.exception`. Cegueira operacional total em produção.
- [x] **C6. Zero validação numérica nos schemas** — todos os `app/schemas/*.py`: aceita `preco: -10`, `rendimento_g: 0/-500`, `fator_correcao: -1`, margem negativa, etc. Fix: `Field(gt=0)`/`ge=0` em todos os campos numéricos + `senha` com `min_length=8`.

### 🟡 Médios (Fase 1 — fundação para relatórios)

- [ ] **M1. Float para dinheiro** — `models/models.py`: todas as colunas monetárias são `Float`. Migrar para `Numeric(12,4)` + `Decimal` ANTES de ter histórico de relatórios (depois fica caro).
- [x] **M2. N+1 queries generalizadas** ✅ 2026-06-11 — `query_produto_completo()` (selectinload) em produtos/precificação; listas e detalhe de receita com selectinload; índices na migration 004 — nenhum endpoint usa `selectinload`; `GET /produtos/{id}` dispara 30–80 queries. Faltam índices nas FKs (`ingrediente_precos.ingrediente_id`, `receita_ingredientes.*`, `produto_massas.produto_id`, `produto_precos.produto_id`). Pré-requisito para relatórios/gráficos.
- [x] **M3. Ambiguidade de unidades** ✅ 2026-06-11 — DECISÃO: converter no cálculo. `app/routers/unidades.py:fator_unidade()` (kg/L → ×1000) aplicado em custo_unitario_ingrediente, calcular_custo_unitario e historico_custo. ⚠️ AUDITAR após deploy: ingredientes com unidade kg/L cujo quantidade_embalagem já estava em gramas (workaround antigo) terão custo ÷1000 — conferir os cadastros kg/L existentes — custo = `preco/quantidade_embalagem`, consumo = `quantidade_g`; se o usuário cadastra embalagem em kg e usa g na receita, custo sai 1000× errado. Não há conversão nem validação. ⚠️ DECISÃO PENDENTE do usuário: normalizar tudo para g/ml na escrita OU converter por unidade no cálculo (afeta dados existentes em produção).
- [x] **M4. UNIQUE em `produto_precos`** ✅ 2026-06-11 — migration 004 (dedupe + constraint) + UniqueConstraint no model — race no check-then-insert (`precificacao.py:129-134`) cria preço duplicado por canal. Idem race no register (IntegrityError → 500).
- [x] **M5. Auth sem proteção** ✅ 2026-06-11 — `app/ratelimit.py` (RateLimiter compartilhado); login 10/5min e register 5/h por IP; IntegrityError no register → 400; `sub` inválido no JWT → 401. *Resta: refresh token (JWT ainda expira em 30min) e register ainda revela e-mails.*
- [x] **M6.** ✅ 2026-06-11 — PUTs com `exclude_unset=True` (ingredientes, embalagens, precificação, custos fixos, colaboradores); receitas usa `model_fields_set` para `tipo`. Enviar null limpa o campo.
- [x] **M7.** ✅ 2026-06-11 — `_extrair_texto_excel()` via openpyxl (requirements: `openpyxl>=3.1.0`); detecta por content-type e extensão.
- [x] **M8.** ✅ 2026-06-11 — `_parse(resp, chave_lista)` valida objeto + lista esperada não-vazia; itens não-dict filtrados; resposta vazia → 422 (max_tokens 4096 já estava).

### 🔵 Menores (oportunista)

- `ingredientes.py:23-27`: `preco_mais_recente()` é código morto; `sorted(ing.precos)` espalhado é redundante (relationship já tem `order_by desc`).
- `auth/utils.py:41-47`: `sub` não-numérico → ValueError não capturado → 500 em vez de 401.
- `datetime.utcnow()` deprecado + DateTime sem timezone em todo o models.py.
- 4 implementações duplicadas de "custo unitário pelo preço mais recente" (ingredientes/embalagens/receitas/produtos) com variações `== 0` vs `> 0`.
- Soft delete inconsistente entre módulos; Dockerfile roda alembic no boot mas deploy real (nixpacks) não usa o Dockerfile.
- Zero testes automatizados no repo.

### ✅ Pontos fortes confirmados na revisão
Multi-tenancy disciplinado nas leituras (todos os SELECTs raiz filtram `user_id`), estrutura limpa router/schema/model, custos calculados on-the-fly, `historico-custo` em produtos.py é o código mais maduro (batch loading correto — usar como modelo).

---

## Próximos passos

- [x] Configurar variáveis de ambiente no EasyPanel
- [x] Testar conexão com banco `quantum`
- [x] Executar `alembic upgrade head` para criar tabelas
- [x] Testar endpoints via Swagger em https://api.quantumcalc.com.br/docs
- [x] Receita tipo livre (migration 002 aplicada em produção)
- [x] Produtos: seção unificada "Preparações"
- [x] Importação via IA (routers/ia.py + anthropic no requirements)
- [x] ANTHROPIC_API_KEY configurada no EasyPanel (IA ativa)
- [x] Campo `marca` em ingredientes + migration 003 + prompt IA normalizado
- [x] **Auditoria e correção de bugs do fluxo completo** (2026-05-29)
  - `schemas/produtos.py`: `ComponenteOut` dividido em `PrepOut` (+ `receita_id`), `IngAvulsoOut` (+ `ingrediente_id`), `EmbOut` (+ `embalagem_id`) — fix crítico de edição de produto
  - `routers/produtos.py`: `calcular_produto` atualizado para popular `receita_id`, `ingrediente_id`, `embalagem_id` nos novos schemas
  - `routers/precificacao.py`: IDOR corrigido em `deletar_preco_produto` — agora valida `Produto.user_id == user.id`
  - `routers/precificacao.py`: `listar_precos_produto` filtra canais inativos (`if not pp.canal.ativo: continue`)
- [ ] Implementar relatórios de margem e custos fixos
- [ ] Habilitar autoDeploy no EasyPanel

---

## Continuação — Fase 2 (próxima sessão)

> Branch de trabalho: `claude/sharp-noether-6ml8uh` (mesma dos dois repos)

### O que foi entregue na sessão de 2026-06-11 (Fase 0 + parte da Fase 1)

**Backend (6 commits, branch pushed):**
- `app/routers/ownership.py` — helper `validar_ids_do_usuario` (IDOR fix C1/C2)
- `app/routers/unidades.py` — `fator_unidade()` para conversão kg/L → g/ml no cálculo
- `app/routers/ia.py` — endpoints `def` (threadpool, não-bloqueante), rate limit 10/10min, limite 15MB, max_tokens 4096
- `app/routers/receitas.py` — ownership no PUT, selectinload no detalhar, fator_unidade no custo unitário
- `app/routers/produtos.py` — `_validar_componentes`, `query_produto_completo` (N+1 fix), fator_unidade no histórico
- `app/routers/ingredientes.py` — fator_unidade em `calcular_custo_unitario`
- `app/main.py` — logger no exception handler global
- `app/schemas/*.py` — validação numérica `Field(gt=0/ge=0)`, senha `min_length=8`
- `app/models/models.py` — `UniqueConstraint` em `produto_precos`
- `migrations/versions/004_indices_e_unique_precos.py` — dedupe + UNIQUE + 17 índices em FK

**⚠️ Ações pendentes antes do próximo deploy (responsabilidade do usuário):**
1. `alembic upgrade head` em produção (migration 004 ainda não aplicada)
2. Auditar ingredientes com unidade `kg` ou `L` em produção — o novo `fator_unidade()` pode mudar o custo deles se `quantidade_embalagem` já estava em gramas como workaround
3. Testar fluxo de importação de nota fiscal — a validação numérica nova (gt=0) rejeita itens com quantidade 0 que a IA ocasionalmente retorna

### Onde continuar

**Fase 2 — Features de relatório (prioridade):**
1. [x] **Endpoint `GET /precificacao/relatorio-margem`** ✅ 2026-06-11 (branch `claude/keen-ptolemy-mmed2k`) — agrega por produto ativo todos os canais ativos: `margem_real_pct = (1 − taxas − custo/preço_praticado) × 100`, `preco_praticado = preco_final ou preco_sugerido`, `lucro_unitario`. Em `precificacao.py` (não `/produtos/...`) para evitar import circular de `calcular_preco_sugerido` e colisão com rota `/produtos/{id}`.
2. [ ] Extrair lógica de cálculo de custo como função reutilizável (hoje duplicada entre `calcular_produto` e `historico_custo`)
3. [ ] Endpoint de snapshot de custo por produto para série temporal (base para gráficos de evolução)

**Fixes críticos descobertos em teste funcional (2026-06-11, mesma branch):**
- `POST /ingredientes/{id}/precos` e `POST /embalagens/{id}/precos` retornavam **500 sempre**: `custo_unitario` obrigatório sem default no schema Out, validado antes de ser setado → default `0.0` adicionado
- `criar/detalhar/atualizar` de receitas e produtos: `Detalhe.model_validate(orm)` validava relacionamentos ORM contra schemas de campos calculados (`ingrediente_nome`, `custo`...) → 500. Agora a resposta é construída como `Detalhe(**Out.model_validate(orm).model_dump(), **calc)`
- Smoke test completo (sqlite + TestClient): register → ingrediente+preço → embalagem+preço → receita → produto → precificação → relatorio-margem ✓ (matemática conferida)

**Fase 1 restante (antes de Fase 2):**
- M1: Migrar colunas monetárias de `Float` → `Numeric(12,4)` (pré-requisito para relatórios precisos)
- M5: Rate limiting em login/register (brute force)
- M6: `PUT` com `exclude_unset=True` em vez de `exclude_none=True` (permite limpar campos opcionais)
- M7: Importação Excel — usar `openpyxl` para `.xlsx` (hoje envia lixo binário ao Claude)
- M8: Parsing IA robusto — validar JSON antes de repassar ao frontend, tratar IndexError em `resp.content[0]`

**Fase 3 (depois):**
- Alerta de margem corroída no Dashboard
- Rateio de custos fixos por produto
- Simulador "e se" com sliders de margem
- Ficha técnica exportável (PDF)
- Modo offline com fila de escrita (pós-TanStack Query)
