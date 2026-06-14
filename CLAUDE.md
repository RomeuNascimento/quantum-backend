# Quantum Backend — CLAUDE.md

## Estado do Projeto

**Criado em:** 2026-05-20
**Última sessão:** 2026-06-14 (branch `claude/keen-goldberg-m8aqqx` — **Água** como ingrediente neutro: semeada no register + garantida na 1ª listagem; sem preço → custo 0. SEM migration — só deploy do backend)
**Penúltima:** 2026-06-13 — segurança esforço médio COMPLETA (`/docs` off · taxas canal < 100% · revogação JWT migration 008 · rate limiter Redis opcional)
**Próxima sessão:** decisão OVO/ÓLEO por unidade vs peso (ver nota abaixo); alertas proativos de margem/preço; auditar ingredientes kg/L em produção; refresh token (JWT 30min); conferir X-Forwarded-For em produção

---

## Sessão 2026-06-14 — Água (ingrediente neutro)

> Branch `claude/keen-goldberg-m8aqqx`. **Sem migration** — só deploy do backend.

- `app/routers/ingredientes.py`: `garantir_agua(db, user_id)` cria um ingrediente
  **"Água"** (unidade `ml`, sem preço → custo 0) se o usuário ainda não tem (match por
  nome normalizado `agua`). Chamada no `listar` (cobre contas já existentes, idempotente —
  cria 1× só) e no `auth/register` (contas novas já nascem com ela).
- Custo 0 sai de graça: `custo_unitario_de_preco(None,...)` já retorna 0.0 — água sem
  preço soma 0 na receita. É um ingrediente comum (aparece no seletor), só que pronto.
- `tests/test_agua.py` (3 testes): vem pronta sem custo, não duplica, soma 0 na receita.
- Frontend: nenhuma mudança — água aparece sozinha no seletor de ingredientes da receita.

> **DÚVIDA EM ABERTO — OVO e ÓLEO (unidade vs peso):** receita pede "3 ovos" (contagem,
> `unidade=unid`) mas às vezes ovo é medido em peso (g). Hoje o ingrediente tem UMA
> unidade só. Ver análise/decisão no fim do CLAUDE.md do frontend (sessão de unidades).
> Óleo: `ml`/`L` ok hoje (consumo em ml); ressalva da densidade (~0,92 g/ml) ignorada
> e o gotcha kg/L do M3 ainda valem.
**Status:** PRODUÇÃO — backend rodando em api.quantumcalc.com.br

---

## Sessão 2026-06-13 (parte 3) — Segurança esforço médio (parcial)

> Branch `claude/keen-goldberg-m8aqqx`. Dois itens da lista "pendências da auditoria
> (esforço médio)" implementados e cobertos por teste (`tests/test_canal_taxas.py`).

**`/docs`, `/redoc`, `/openapi.json` desligados por padrão:**
- `Settings.enable_docs: bool = False` (`app/database.py`); `main.py` passa
  `docs_url/redoc_url/openapi_url = None` quando off. Esconde o schema da API em produção.
- ⚠️ **Após o deploy, `https://api.quantumcalc.com.br/docs` vira 404.** Para reativar
  (staging/depuração): `ENABLE_DOCS=true` no EasyPanel. Documentado no `.env.example`.

**Validação da soma de taxas do canal < 100%:**
- `CanalCreate` (Pydantic `model_validator`) → 422 se plataforma+cartão+imposto ≥ 100%.
- `atualizar_canal` valida a soma após o merge dos campos parciais → 400.
- `validar_margem_viavel()` em `criar/atualizar_preco_produto` → 400 se margem+taxas ≥ 100%
  (antes o preço sugerido caía para R$ 0 silenciosamente).

**Revogação de JWT (jti + denylist + token_version) — migration 008:**
- Token agora carrega `jti` (uuid único) + `tv` (token_version do usuário na emissão).
  `criar_token_usuario(user)` em `auth/utils.py` substitui `criar_token({"sub":...})`.
- `get_usuario_atual` rejeita (401) se `tv` do token ≠ `user.token_version` (revogação
  em massa) **ou** se o `jti` está na denylist `revoked_tokens` (revogação individual).
- `POST /auth/logout` — denylist do jti do token atual (logout de um dispositivo);
  idempotente + expurgo oportunista de jti expirados.
- `POST /auth/logout-all` — bump em `token_version` (derruba todas as sessões).
- `POST /auth/alterar-senha` — verifica senha atual, troca, bump token_version
  (derruba as outras sessões) e devolve token novo p/ o dispositivo atual.
- **Retrocompat:** token antigo sem `tv`/`jti` segue válido enquanto `token_version==0`
  (e expira em 30 min de qualquer forma). Testado em `tests/test_revogacao.py` (5 testes).
- ⚠️ **Requer `alembic upgrade head` (migration 008)** em produção — adiciona
  `users.token_version` (server_default 0) + tabela `revoked_tokens`. Upgrade/downgrade
  validados em sqlite isolado.
- Frontend: `authStore.logout()` chama `/auth/logout` (best-effort, sem recursão de 401).

**Rate limiter com backend Redis opcional (sem migration):**
- `app/ratelimit.py`: `RateLimiter` agora usa Redis (sorted set, janela deslizante
  por chave) quando `REDIS_URL` está setada — consistente entre múltiplos
  workers/réplicas. Sem `REDIS_URL`, cai no dict em memória (comportamento atual).
- `get_redis()` é lazy singleton: sem URL → None (memória); URL setada mas Redis
  fora do ar no boot → loga aviso e degrada p/ memória (fail-open). Se o Redis cair
  em runtime, a chamada faz fallback p/ memória em vez de derrubar a request.
- Rejeição faz `zrem` do próprio membro (paridade com memória: tentativa rejeitada
  não estende a punição além da janela).
- `tests/test_ratelimit.py` (5 testes, via fakeredis): bloqueio, isolamento por
  chave, não-extensão da punição, fallback memória, fallback em runtime.
- ⚠️ **Só com `REDIS_URL` setada o `--workers N` > 1 (ou réplicas) é seguro.**
  Sem ela, o startCommand DEVE continuar com 1 worker.

**Infra de teste:** `conftest.py` ganhou fixture autouse que zera os rate limiters
em memória por módulo (estado vazava entre módulos e disparava 429 espúrio).

**Pendências de deploy (usuário):** `alembic upgrade head` (migration 008) + disparar
deploy do backend no EasyPanel; se quiser manter o Swagger acessível em produção, setar
`ENABLE_DOCS=true` antes. Para escalar workers, provisionar Redis e setar `REDIS_URL`
(opcional — sem ela tudo segue funcionando com 1 worker).

---

## Sessão 2026-06-13 (parte 2) — Embalagens + plano mensal

**Embalagens (PR #3):**
- `PROMPT_NOTA` classifica cada item com `tipo: ingrediente|embalagem` (caixas, sacos,
  formas, descartáveis); normalização defensiva (inválido → ingrediente)
- `POST /ingredientes/{id}/converter-em-embalagem` e
  `POST /embalagens/{id}/converter-em-ingrediente` — copiam histórico de preços,
  original vira `ativo=False` (receitas/produtos existentes seguem calculando)
- `tests/test_conversao.py` (ida/volta/tenant) — suíte com 18 testes

**Plano mensal Stripe (PR #4):**
- `/billing/checkout` aceita `{plano: anual|mensal}`; price mensal via env
  `STRIPE_PRICE_ID_MENSAL` (sem ela, só anual — rollout controlado)
- `GET /billing/planos`: valores reais do Stripe (cache em processo)
- Webhook: fallback de validade 368d→35d provisórios (368 daria 1 ano grátis a
  assinante mensal); pagamento só ESTENDE validade, nunca encurta
- `setup_stripe.py` cria também o preço mensal R$ 19,90

**⚠️ Pendências de deploy (usuário):**
1. Disparar deploy do backend no EasyPanel (PRs #3 e #4 mergeados, sem migration nova)
2. Para ativar o mensal: `STRIPE_API_KEY=rk_live_... python scripts/setup_stripe.py`
   → configurar `STRIPE_PRICE_ID_MENSAL` no EasyPanel → redeploy
3. Frontend: deploy também pendente (PRs de UX/embalagens/orçamento mergeados)

---

## Sessão 2026-06-13 — Auditoria de segurança (squad cyber-chief) + correções

> Auditoria estática completa pelo squad cyber-chief. Correções de esforço baixo
> implementadas, mergeadas (PR #1) e **deployadas em produção em 2026-06-13**
> (migration 007 aplicada pelo usuário do PC local — psycopg2-binary no Windows).

**Corrigido e em produção:**
- **Idempotência do webhook Stripe** — tabela `stripe_events` (UNIQUE event_id, migration `007_stripe_events.py`) + short-circuit; Stripe entrega at-least-once. Coberto por `test_webhook_idempotente` (15 testes passando)
- **IP real atrás do proxy** — `_ip()` em `auth/router.py` usa o último valor do `X-Forwarded-For` (antes: todos os clientes no bucket do IP do proxy)
- **Hardening IA** — magic bytes no upload (`_detectar_media_type`; content-type do cliente não é confiável) + `BLOCO_SEGURANCA` nos prompts + conteúdo textual em `<documento_do_usuario>` (anti prompt injection)
- **Anti-enumeração por timing no login** — `_DUMMY_HASH` verificado quando e-mail não existe
- **CORS** — métodos/headers explícitos (antes wildcard com credentials)
- **`criar_preco_produto`** — race do check-then-insert → 400 via IntegrityError (antes 500)
- **RateLimiter** — expurgo de chaves antigas (dict crescia sem limite)

**Pendências da auditoria (esforço médio):**
- [x] Rate limiter em Redis ✅ 2026-06-13 (parte 3) — backend Redis opcional via `REDIS_URL` (sorted set), fallback em memória; só com Redis o `--workers N` > 1 é seguro
- [x] `jti` + denylist de JWT ✅ 2026-06-13 (parte 3) — token_version (logout-all / troca de senha) + denylist por jti (logout); migration 008
- [x] Proteger/desabilitar `/docs` (Swagger) em produção ✅ 2026-06-13 (parte 3) — `enable_docs` off por padrão
- [x] Validar soma de taxas do canal < 100% ✅ 2026-06-13 (parte 3) — 422/400 + guard de margem+taxas
- Conferir em produção qual IP chega no X-Forwarded-For (validar fix do rate limit)

**Pontos fortes confirmados pela auditoria:** multi-tenancy sem furos (varredura nos 9 routers), zero SQL raw, IDOR fixes de junho completos, catálogo da IA corretamente escopado ao tenant.

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
- [x] **Matching de ingredientes nota fiscal ↔ catálogo via IA** (2026-06-12, branch `claude/practical-cray-vksesn`)
  - `ia.py`: os dois endpoints injetam o catálogo de ingredientes ativos do usuário no prompt (`_catalogo_usuario`, máx. 300 itens)
  - `POST /ia/nota-fiscal`: resposta ganha `ingrediente_id_sugerido` por item (id do catálogo ou null) — IA vincula mesmo insumo de marca diferente, não vincula insumo distinto; `_validar_ids_sugeridos` descarta ids alucinados
  - `POST /ia/receitas`: prompt instrui a reutilizar os nomes EXATOS do catálogo (evita "açúcar" vs "açúcar refinado" duplicando)
  - Frontend: revisão da nota ganhou select "Vincular a:" pré-selecionado com a sugestão da IA
- [x] **Billing — assinatura anual via Stripe** (2026-06-12, branch `claude/practical-cray-vksesn`)
  - `app/routers/billing.py`: `GET /billing/status`, `POST /billing/checkout`, `POST /billing/portal`, `POST /billing/webhook` (assinatura verificada via `STRIPE_WEBHOOK_SECRET`)
  - Modelo: trial de 7 dias para contas novas; contas pré-existentes ficaram `ativa` sem validade (migration 006); validade = fim do período pago + 3 dias de carência
  - **Setup Stripe executado em 2026-06-12** (live): produto "Quantum — Plano Anual", `STRIPE_PRICE_ID=price_1ThTKO5aXvvE532vI8CgfUte`, webhook `https://api.quantumcalc.com.br/billing/webhook` — secret configurado no EasyPanel
  - **Paywall enforcement:** `require_assinatura_ativa` (HTTP 402 se `status_efetivo == 'vencida'`) aplicado a todos os routers de negócio em `main.py`; `auth` e `billing` ficam livres (usuário vencido precisa conseguir pagar)
  - `tests/test_billing.py`: 11 testes (status_efetivo puro + endpoint + paywall 402/liberação); infra de teste extraída para `tests/db.py` + `tests/conftest.py` (engine único — dois módulos com engine próprio conflitavam)
  - Frontend correspondente: página `/assinatura`, banners no Dashboard, `PaywallGate` no PrivateRoute, 402 → redirect em `client.js`
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

# Billing (obrigatório para /billing/* — sem elas os endpoints retornam 503)
STRIPE_API_KEY=<chave restrita rk_live_... — ver no EasyPanel>
STRIPE_PRICE_ID=price_1ThTKO5aXvvE532vI8CgfUte
STRIPE_WEBHOOK_SECRET=<whsec_... — ver no EasyPanel>
FRONTEND_URL=https://quantumcalc.com.br   # opcional, este é o padrão

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
  - ⚠️ **1 worker** enquanto não houver `REDIS_URL` (rate limit em memória não é
    compartilhado entre processos). Com Redis provisionado + `REDIS_URL` setada,
    pode-se usar `--workers N`.
- **Domínio:** `api.quantumcalc.com.br` porta 8000, HTTPS true
- **autoDeploy:** false (deploy manual via painel ou API)

> **Migrations:** rodar manualmente do local com todas as env vars:
> `DATABASE_URL=postgresql+psycopg2://...@72.61.132.202:5432/quantum JWT_SECRET=... alembic upgrade head`
> O banco externo fica em `72.61.132.202:5432` (porta 5432 exposta no EasyPanel).
>
> ✅ **Migration 007 APLICADA em produção 2026-06-13** (`stripe_events`) — rodada
> do Windows do usuário; no Windows, `psycopg2` não compila: usar
> `pip install psycopg2-binary` e instalar o requirements sem a linha do psycopg2.
> Do PC local o host é `72.61.132.202:5432` (não `quantum_quantum-db`).
>
> ✅ **APLICADO em produção 2026-06-12** — `alembic upgrade head` rodado com
> sucesso (banco saiu de 003 → 006). Migrations 004 (índices + UNIQUE
> produto_precos), 005 (Float → NUMERIC(12,4)) e 006 (colunas de billing;
> contas existentes → 'ativa') estão no banco de produção. Backend e frontend
> deployados na mesma data.
>
> ⚠️ **Armadilha encontrada ao rodar:** havia um arquivo de migration órfão
> `004_user_plano_expira.py` na pasta local (untracked, não estava no git) que
> causava erro `Multiple head revisions are present`. Removido da pasta local
> antes do upgrade. Se reaparecer "multiple heads", procure migrations
> duplicadas com mesmo `down_revision` em `migrations/versions/`.

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

- [x] **M1. Float para dinheiro** ✅ 2026-06-12 (branch `claude/practical-cray-vksesn`) — 21 colunas monetárias/quantitativas migradas de `Float` → `Numeric(12, 4, asdecimal=False)` (alias `Dinheiro` em models.py) + migration `005_money_float_to_numeric.py`. **Decisão:** `asdecimal=False` — NUMERIC exato no banco, mas o SQLAlchemy devolve `float` no Python, mantendo intactos todos os cálculos dos routers e os schemas Pydantic (evita TypeError de `Decimal × float`).
- [x] **M2. N+1 queries generalizadas** ✅ 2026-06-11 — `query_produto_completo()` (selectinload) em produtos/precificação; listas e detalhe de receita com selectinload; índices na migration 004 — nenhum endpoint usa `selectinload`; `GET /produtos/{id}` dispara 30–80 queries. Faltam índices nas FKs (`ingrediente_precos.ingrediente_id`, `receita_ingredientes.*`, `produto_massas.produto_id`, `produto_precos.produto_id`). Pré-requisito para relatórios/gráficos.
- [x] **M3. Ambiguidade de unidades** ✅ 2026-06-11 — DECISÃO: converter no cálculo. `app/routers/unidades.py:fator_unidade()` (kg/L → ×1000) aplicado em custo_unitario_ingrediente, calcular_custo_unitario e historico_custo. ⚠️ AUDITAR após deploy: ingredientes com unidade kg/L cujo quantidade_embalagem já estava em gramas (workaround antigo) terão custo ÷1000 — conferir os cadastros kg/L existentes — custo = `preco/quantidade_embalagem`, consumo = `quantidade_g`; se o usuário cadastra embalagem em kg e usa g na receita, custo sai 1000× errado. Não há conversão nem validação. ⚠️ DECISÃO PENDENTE do usuário: normalizar tudo para g/ml na escrita OU converter por unidade no cálculo (afeta dados existentes em produção).
- [x] **M4. UNIQUE em `produto_precos`** ✅ 2026-06-11 — migration 004 (dedupe + constraint) + UniqueConstraint no model — race no check-then-insert (`precificacao.py:129-134`) cria preço duplicado por canal. Idem race no register (IntegrityError → 500).
- [x] **M5. Auth sem proteção** ✅ 2026-06-11 — `app/ratelimit.py` (RateLimiter compartilhado); login 10/5min e register 5/h por IP; IntegrityError no register → 400; `sub` inválido no JWT → 401. *Resta: refresh token (JWT ainda expira em 30min) e register ainda revela e-mails.*
- [x] **M6.** ✅ 2026-06-11 — PUTs com `exclude_unset=True` (ingredientes, embalagens, precificação, custos fixos, colaboradores); receitas usa `model_fields_set` para `tipo`. Enviar null limpa o campo.
- [x] **M7.** ✅ 2026-06-11 — `_extrair_texto_excel()` via openpyxl (requirements: `openpyxl>=3.1.0`); detecta por content-type e extensão.
- [x] **M8.** ✅ 2026-06-11 — `_parse(resp, chave_lista)` valida objeto + lista esperada não-vazia; itens não-dict filtrados; resposta vazia → 422 (max_tokens 4096 já estava).

### 🔵 Menores (oportunista)

- [x] `preco_mais_recente()` código morto removido ✅ 2026-06-12
- `auth/utils.py:41-47`: `sub` não-numérico → ValueError não capturado → 500 em vez de 401.
- `datetime.utcnow()` deprecado + DateTime sem timezone em todo o models.py.
- [x] 4 implementações duplicadas de custo unitário → **`app/routers/custos.py`** ✅ 2026-06-12 (`custo_unitario_de_preco`, `custo_unitario_embalagem_de_preco`, `preco_mais_recente`) — usadas por ingredientes/embalagens/receitas/produtos (inclusive `historico_custo`)
- Soft delete inconsistente entre módulos; Dockerfile roda alembic no boot mas deploy real (nixpacks) não usa o Dockerfile.
- [x] Zero testes → **`tests/test_smoke.py`** ✅ 2026-06-12 (sqlite in-memory + TestClient): fluxo completo register→ingrediente→embalagem→receita→produto→precificação iFood→relatório-margem com matemática conferida + anti-enumeração de e-mail + histórico de custo. Rodar: `DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/ -q`

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
2. [x] Extrair lógica de cálculo de custo como função reutilizável ✅ 2026-06-12 — `app/routers/custos.py` unifica a fórmula preço→custo unitário usada nos 4 módulos (a duplicação real); `calcular_produto` (estado atual) e `historico_custo` (por data) mantêm percursos próprios por natureza, mas agora compartilham a fórmula
3. [ ] Endpoint de snapshot de custo por produto para série temporal — **avaliar se ainda é necessário**: `GET /produtos/{id}/historico-custo` já reconstrói a série inteira a partir do histórico de preços (e alimenta o gráfico do frontend); snapshot persistido só se a performance degradar
- M5 restante: register não revela mais e-mails ✅ 2026-06-12 (mensagem vaga anti-enumeração); falta apenas refresh token (JWT 30min) — requer mudança coordenada com o frontend

**Fixes críticos descobertos em teste funcional (2026-06-11, mesma branch):**
- `POST /ingredientes/{id}/precos` e `POST /embalagens/{id}/precos` retornavam **500 sempre**: `custo_unitario` obrigatório sem default no schema Out, validado antes de ser setado → default `0.0` adicionado
- `criar/detalhar/atualizar` de receitas e produtos: `Detalhe.model_validate(orm)` validava relacionamentos ORM contra schemas de campos calculados (`ingrediente_nome`, `custo`...) → 500. Agora a resposta é construída como `Detalhe(**Out.model_validate(orm).model_dump(), **calc)`
- Smoke test completo (sqlite + TestClient): register → ingrediente+preço → embalagem+preço → receita → produto → precificação → relatorio-margem ✓ (matemática conferida)

**Fase 1 restante (antes de Fase 2):**
- [x] M1: ✅ 2026-06-12 (branch `claude/practical-cray-vksesn`) — `Float` → `Numeric(12, 4, asdecimal=False)` em todas as 21 colunas monetárias/quantitativas + migration 005. ⚠️ Requer `alembic upgrade head` em produção (junto da 004 pendente).
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
