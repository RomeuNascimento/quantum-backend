# Quantum Backend — CLAUDE.md

## Estado do Projeto

**Criado em:** 2026-05-20
**Última sessão:** 2026-05-20
**Status:** Estrutura inicial criada, aguardando deploy no EasyPanel

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

---

## Stack

- **Framework:** FastAPI (Python 3.11)
- **ORM:** SQLAlchemy 2.x + Alembic (migrations)
- **Auth:** JWT (python-jose + passlib bcrypt)
- **Banco:** PostgreSQL (psycopg2)
- **Deploy:** EasyPanel → https://api.quantumcalc.com.br

---

## Variáveis de Ambiente (EasyPanel)

```
DATABASE_URL=postgresql+psycopg2://postgres:SENHA@panel.quantumcalc.com.br:5433/quantum_prod
JWT_SECRET=<gerar com: python -c "import secrets; print(secrets.token_hex(32))">
JWT_ALGORITHM=HS256
JWT_EXPIRATION=30
ALLOW_ORIGINS=https://quantumcalc.com.br
```

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
│   ├── produtos.py       — CRUD + cálculo custo composto
│   ├── precificacao.py   — Canais + preços sugeridos
│   └── custos_fixos.py   — CRUD custos fixos
└── schemas/
    └── (um arquivo por módulo)
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

---

## Deploy EasyPanel

1. Criar novo serviço "App" apontando para o repo GitHub
2. Configurar as variáveis de ambiente acima
3. Build command: `pip install -r requirements.txt && alembic upgrade head`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
5. Domínio: `api.quantumcalc.com.br`

---

## Próximos passos

- [ ] Configurar variáveis de ambiente no EasyPanel
- [ ] Testar conexão com banco `quantum_prod`
- [ ] Executar `alembic upgrade head` para criar tabelas
- [ ] Testar endpoints via Swagger em https://api.quantumcalc.com.br/docs
- [ ] Implementar upload de nota fiscal para leitura via IA (futuro)
- [ ] Implementar relatórios de margem e custos fixos (futuro)
