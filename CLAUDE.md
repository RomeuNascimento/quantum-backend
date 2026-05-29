# Quantum Backend — CLAUDE.md

## Estado do Projeto

**Criado em:** 2026-05-20
**Última sessão:** 2026-05-29
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
2. **Custo unitário ingrediente:** `(preco / qtd_embalagem) / fator_correcao` — sempre pelo registro mais recente
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

### Deploy manual via API
```bash
curl -X POST https://panel.quantumcalc.com.br/api/trpc/services.app.deployService \
  -H "Authorization: Bearer <EASYPANEL_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"json":{"projectName":"quantum","serviceName":"backend"}}'
```

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
