"""Criação inicial das tabelas

Revision ID: 001
Revises:
Create Date: 2026-05-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "configuracoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("valor_hora_padrao", sa.Float(), default=0.0),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "colaboradores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("valor_hora", sa.Float(), nullable=False),
        sa.Column("ativo", sa.Boolean(), default=True),
    )

    unidade_enum = sa.Enum("g", "ml", "unid", "kg", "L", name="unidadeenum")
    origem_enum = sa.Enum("manual", "nota_fiscal_ia", name="origemenum")
    periodo_enum = sa.Enum("mensal", "anual", name="periodoenum")
    tipo_receita_enum = sa.Enum("massa", "recheio", name="tiporeceitaenum")

    op.create_table(
        "ingredientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("unidade", unidade_enum, nullable=False),
        sa.Column("fator_correcao", sa.Float(), default=1.0),
        sa.Column("ativo", sa.Boolean(), default=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "ingrediente_precos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ingrediente_id", sa.Integer(), sa.ForeignKey("ingredientes.id"), nullable=False),
        sa.Column("preco", sa.Float(), nullable=False),
        sa.Column("quantidade_embalagem", sa.Float(), nullable=False),
        sa.Column("data_compra", sa.DateTime(), nullable=False),
        sa.Column("origem", origem_enum, default="manual"),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "embalagens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("unidade", unidade_enum, nullable=False),
        sa.Column("ativo", sa.Boolean(), default=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "embalagem_precos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("embalagem_id", sa.Integer(), sa.ForeignKey("embalagens.id"), nullable=False),
        sa.Column("preco", sa.Float(), nullable=False),
        sa.Column("quantidade_embalagem", sa.Float(), nullable=False),
        sa.Column("data_compra", sa.DateTime(), nullable=False),
        sa.Column("origem", origem_enum, default="manual"),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "receitas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("tipo", tipo_receita_enum, nullable=False),
        sa.Column("rendimento_g", sa.Float(), nullable=False),
        sa.Column("ativo", sa.Boolean(), default=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "receita_ingredientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receita_id", sa.Integer(), sa.ForeignKey("receitas.id"), nullable=False),
        sa.Column("ingrediente_id", sa.Integer(), sa.ForeignKey("ingredientes.id"), nullable=False),
        sa.Column("quantidade_g", sa.Float(), nullable=False),
    )

    op.create_table(
        "receita_mo_etapas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receita_id", sa.Integer(), sa.ForeignKey("receitas.id"), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("tempo_min", sa.Float(), nullable=False),
        sa.Column("colaborador_id", sa.Integer(), sa.ForeignKey("colaboradores.id"), nullable=True),
    )

    op.create_table(
        "produtos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("ativo", sa.Boolean(), default=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "produto_massas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("receita_id", sa.Integer(), sa.ForeignKey("receitas.id"), nullable=False),
        sa.Column("quantidade_g", sa.Float(), nullable=False),
    )

    op.create_table(
        "produto_recheios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("receita_id", sa.Integer(), sa.ForeignKey("receitas.id"), nullable=False),
        sa.Column("quantidade_g", sa.Float(), nullable=False),
    )

    op.create_table(
        "produto_ingredientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("ingrediente_id", sa.Integer(), sa.ForeignKey("ingredientes.id"), nullable=False),
        sa.Column("quantidade_g", sa.Float(), nullable=False),
    )

    op.create_table(
        "produto_embalagens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("embalagem_id", sa.Integer(), sa.ForeignKey("embalagens.id"), nullable=False),
        sa.Column("quantidade", sa.Float(), nullable=False),
    )

    op.create_table(
        "produto_mo_montagem",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("tempo_min", sa.Float(), nullable=False),
        sa.Column("colaborador_id", sa.Integer(), sa.ForeignKey("colaboradores.id"), nullable=True),
    )

    op.create_table(
        "canais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("taxa_plataforma_pct", sa.Float(), default=0.0),
        sa.Column("taxa_cartao_pct", sa.Float(), default=0.0),
        sa.Column("imposto_pct", sa.Float(), default=0.0),
        sa.Column("ativo", sa.Boolean(), default=True),
    )

    op.create_table(
        "produto_precos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("canal_id", sa.Integer(), sa.ForeignKey("canais.id"), nullable=False),
        sa.Column("margem_pct", sa.Float(), nullable=False),
        sa.Column("preco_final", sa.Float(), nullable=True),
    )

    op.create_table(
        "custos_fixos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("periodo", periodo_enum, nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("NOW()")),
    )

    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_ingredientes_user", "ingredientes", ["user_id"])
    op.create_index("ix_embalagens_user", "embalagens", ["user_id"])
    op.create_index("ix_receitas_user", "receitas", ["user_id"])
    op.create_index("ix_produtos_user", "produtos", ["user_id"])


def downgrade() -> None:
    op.drop_table("custos_fixos")
    op.drop_table("produto_precos")
    op.drop_table("canais")
    op.drop_table("produto_mo_montagem")
    op.drop_table("produto_embalagens")
    op.drop_table("produto_ingredientes")
    op.drop_table("produto_recheios")
    op.drop_table("produto_massas")
    op.drop_table("produtos")
    op.drop_table("receita_mo_etapas")
    op.drop_table("receita_ingredientes")
    op.drop_table("receitas")
    op.drop_table("embalagem_precos")
    op.drop_table("embalagens")
    op.drop_table("ingrediente_precos")
    op.drop_table("ingredientes")
    op.drop_table("colaboradores")
    op.drop_table("configuracoes")
    op.drop_table("users")
