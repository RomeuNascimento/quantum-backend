from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime,
    ForeignKey, Enum, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum

# M1 (auditoria 2026-06-11): colunas monetárias/quantitativas usam NUMERIC(12,4)
# no banco (precisão exata, sem erro de ponto flutuante no armazenamento), mas
# `asdecimal=False` faz o SQLAlchemy devolver float no Python — evita TypeError
# de Decimal × float nos cálculos dos routers e mantém os schemas Pydantic (float).
Dinheiro = Numeric(12, 4, asdecimal=False)


class UnidadeEnum(str, enum.Enum):
    g = "g"
    ml = "ml"
    unid = "unid"
    kg = "kg"
    L = "L"


class OrigemEnum(str, enum.Enum):
    manual = "manual"
    nota_fiscal_ia = "nota_fiscal_ia"


class PeriodoEnum(str, enum.Enum):
    mensal = "mensal"
    anual = "anual"



# ─── AUTH ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
    # Billing (Stripe): status 'trial' | 'ativa' | 'vencida'
    stripe_customer_id = Column(String(100), nullable=True, index=True)
    assinatura_status = Column(String(20), nullable=False, default="trial")
    assinatura_validade = Column(DateTime, nullable=True)
    # Revogação de JWT em massa: o token carrega o `tv` da emissão; bumpar este
    # contador (logout-all / troca de senha) invalida todas as sessões abertas.
    token_version = Column(Integer, nullable=False, default=0, server_default="0")

    configuracao = relationship("Configuracao", back_populates="user", uselist=False)
    colaboradores = relationship("Colaborador", back_populates="user")
    ingredientes = relationship("Ingrediente", back_populates="user")
    embalagens = relationship("Embalagem", back_populates="user")
    receitas = relationship("Receita", back_populates="user")
    produtos = relationship("Produto", back_populates="user")
    canais = relationship("Canal", back_populates="user")
    custos_fixos = relationship("CustoFixo", back_populates="user")


class Configuracao(Base):
    __tablename__ = "configuracoes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    valor_hora_padrao = Column(Dinheiro, default=0.0)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="configuracao")


class Colaborador(Base):
    __tablename__ = "colaboradores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(120), nullable=False)
    valor_hora = Column(Dinheiro, nullable=False)
    ativo = Column(Boolean, default=True)

    user = relationship("User", back_populates="colaboradores")


# ─── INGREDIENTES ─────────────────────────────────────────────────────────────

class Ingrediente(Base):
    __tablename__ = "ingredientes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(150), nullable=False)
    marca = Column(String(100), nullable=True)
    unidade = Column(Enum(UnidadeEnum), nullable=False)
    fator_correcao = Column(Dinheiro, default=1.0)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="ingredientes")
    precos = relationship("IngredientePreco", back_populates="ingrediente",
                          order_by="desc(IngredientePreco.data_compra)",
                          cascade="all, delete-orphan")


class IngredientePreco(Base):
    __tablename__ = "ingrediente_precos"

    id = Column(Integer, primary_key=True, index=True)
    ingrediente_id = Column(Integer, ForeignKey("ingredientes.id"), nullable=False)
    preco = Column(Dinheiro, nullable=False)
    quantidade_embalagem = Column(Dinheiro, nullable=False)
    data_compra = Column(DateTime, nullable=False)
    origem = Column(Enum(OrigemEnum), default=OrigemEnum.manual)
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    ingrediente = relationship("Ingrediente", back_populates="precos")


# ─── EMBALAGENS ───────────────────────────────────────────────────────────────

class Embalagem(Base):
    __tablename__ = "embalagens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(150), nullable=False)
    unidade = Column(Enum(UnidadeEnum), nullable=False)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="embalagens")
    precos = relationship("EmbalagemPreco", back_populates="embalagem",
                          order_by="desc(EmbalagemPreco.data_compra)",
                          cascade="all, delete-orphan")


class EmbalagemPreco(Base):
    __tablename__ = "embalagem_precos"

    id = Column(Integer, primary_key=True, index=True)
    embalagem_id = Column(Integer, ForeignKey("embalagens.id"), nullable=False)
    preco = Column(Dinheiro, nullable=False)
    quantidade_embalagem = Column(Dinheiro, nullable=False)
    data_compra = Column(DateTime, nullable=False)
    origem = Column(Enum(OrigemEnum), default=OrigemEnum.manual)
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    embalagem = relationship("Embalagem", back_populates="precos")


# ─── RECEITAS ─────────────────────────────────────────────────────────────────

class Receita(Base):
    __tablename__ = "receitas"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(150), nullable=False)
    tipo = Column(String(100), nullable=True)
    rendimento_g = Column(Dinheiro, nullable=False)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="receitas")
    ingredientes = relationship("ReceitaIngrediente", back_populates="receita",
                               cascade="all, delete-orphan")
    etapas_mo = relationship("ReceitaMOEtapa", back_populates="receita",
                             cascade="all, delete-orphan")


class ReceitaIngrediente(Base):
    __tablename__ = "receita_ingredientes"

    id = Column(Integer, primary_key=True, index=True)
    receita_id = Column(Integer, ForeignKey("receitas.id"), nullable=False)
    ingrediente_id = Column(Integer, ForeignKey("ingredientes.id"), nullable=False)
    quantidade_g = Column(Dinheiro, nullable=False)

    receita = relationship("Receita", back_populates="ingredientes")
    ingrediente = relationship("Ingrediente")


class ReceitaMOEtapa(Base):
    __tablename__ = "receita_mo_etapas"

    id = Column(Integer, primary_key=True, index=True)
    receita_id = Column(Integer, ForeignKey("receitas.id"), nullable=False)
    descricao = Column(String(200), nullable=False)
    tempo_min = Column(Dinheiro, nullable=False)
    colaborador_id = Column(Integer, ForeignKey("colaboradores.id"), nullable=True)

    receita = relationship("Receita", back_populates="etapas_mo")
    colaborador = relationship("Colaborador")


# ─── PRODUTOS ─────────────────────────────────────────────────────────────────

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(150), nullable=False)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="produtos")
    massas = relationship("ProdutoMassa", back_populates="produto")
    recheios = relationship("ProdutoRecheio", back_populates="produto")
    ingredientes = relationship("ProdutoIngrediente", back_populates="produto")
    embalagens = relationship("ProdutoEmbalagem", back_populates="produto")
    mo_montagem = relationship("ProdutoMOMontagem", back_populates="produto")
    precos = relationship("ProdutoPreco", back_populates="produto")


class ProdutoMassa(Base):
    __tablename__ = "produto_massas"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    receita_id = Column(Integer, ForeignKey("receitas.id"), nullable=False)
    quantidade_g = Column(Dinheiro, nullable=False)

    produto = relationship("Produto", back_populates="massas")
    receita = relationship("Receita")


class ProdutoRecheio(Base):
    __tablename__ = "produto_recheios"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    receita_id = Column(Integer, ForeignKey("receitas.id"), nullable=False)
    quantidade_g = Column(Dinheiro, nullable=False)

    produto = relationship("Produto", back_populates="recheios")
    receita = relationship("Receita")


class ProdutoIngrediente(Base):
    __tablename__ = "produto_ingredientes"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    ingrediente_id = Column(Integer, ForeignKey("ingredientes.id"), nullable=False)
    quantidade_g = Column(Dinheiro, nullable=False)

    produto = relationship("Produto", back_populates="ingredientes")
    ingrediente = relationship("Ingrediente")


class ProdutoEmbalagem(Base):
    __tablename__ = "produto_embalagens"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    embalagem_id = Column(Integer, ForeignKey("embalagens.id"), nullable=False)
    quantidade = Column(Dinheiro, nullable=False)

    produto = relationship("Produto", back_populates="embalagens")
    embalagem = relationship("Embalagem")


class ProdutoMOMontagem(Base):
    __tablename__ = "produto_mo_montagem"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    descricao = Column(String(200), nullable=False)
    tempo_min = Column(Dinheiro, nullable=False)
    colaborador_id = Column(Integer, ForeignKey("colaboradores.id"), nullable=True)

    produto = relationship("Produto", back_populates="mo_montagem")
    colaborador = relationship("Colaborador")


# ─── PRECIFICAÇÃO ─────────────────────────────────────────────────────────────

class Canal(Base):
    __tablename__ = "canais"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    taxa_plataforma_pct = Column(Dinheiro, default=0.0)
    taxa_cartao_pct = Column(Dinheiro, default=0.0)
    imposto_pct = Column(Dinheiro, default=0.0)
    ativo = Column(Boolean, default=True)

    user = relationship("User", back_populates="canais")
    precos = relationship("ProdutoPreco", back_populates="canal")


class ProdutoPreco(Base):
    __tablename__ = "produto_precos"
    __table_args__ = (
        UniqueConstraint("produto_id", "canal_id", name="uq_produto_precos_produto_canal"),
    )

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    canal_id = Column(Integer, ForeignKey("canais.id"), nullable=False)
    margem_pct = Column(Dinheiro, nullable=False)
    preco_final = Column(Dinheiro, nullable=True)

    produto = relationship("Produto", back_populates="precos")
    canal = relationship("Canal", back_populates="precos")


# ─── CUSTOS FIXOS ─────────────────────────────────────────────────────────────

class CustoFixo(Base):
    __tablename__ = "custos_fixos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(150), nullable=False)
    valor = Column(Dinheiro, nullable=False)
    periodo = Column(Enum(PeriodoEnum), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="custos_fixos")


# ─── BILLING ──────────────────────────────────────────────────────────────────

class StripeEvent(Base):
    """Eventos de webhook já processados — o Stripe entrega at-least-once,
    então o event_id precisa ser idempotente (UNIQUE) para evitar reprocesso."""
    __tablename__ = "stripe_events"

    id = Column(Integer, primary_key=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    tipo = Column(String(100), nullable=False)
    recebido_em = Column(DateTime, default=datetime.utcnow)


# ─── REVOGAÇÃO DE JWT ─────────────────────────────────────────────────────────

class RevokedToken(Base):
    """Denylist de tokens revogados individualmente (logout de um dispositivo).
    Guarda o `jti` do JWT até a sua expiração natural — depois disso pode ser
    expurgado, pois o token já não é aceito de qualquer forma."""
    __tablename__ = "revoked_tokens"

    jti = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expira_em = Column(DateTime, nullable=False)
    revogado_em = Column(DateTime, default=datetime.utcnow)
