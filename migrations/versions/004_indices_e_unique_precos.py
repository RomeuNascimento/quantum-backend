"""Índices nas FKs mais consultadas + UNIQUE em produto_precos (produto_id, canal_id)

Revision ID: 004
Revises: 003
Create Date: 2026-06-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicatas existentes antes do UNIQUE (mantém o registro mais recente)
    op.execute(
        """
        DELETE FROM produto_precos a
        USING produto_precos b
        WHERE a.produto_id = b.produto_id
          AND a.canal_id = b.canal_id
          AND a.id < b.id
        """
    )
    op.create_unique_constraint(
        "uq_produto_precos_produto_canal", "produto_precos", ["produto_id", "canal_id"]
    )

    op.create_index("ix_ingrediente_precos_ingrediente", "ingrediente_precos", ["ingrediente_id"])
    op.create_index("ix_embalagem_precos_embalagem", "embalagem_precos", ["embalagem_id"])
    op.create_index("ix_receita_ingredientes_receita", "receita_ingredientes", ["receita_id"])
    op.create_index("ix_receita_ingredientes_ingrediente", "receita_ingredientes", ["ingrediente_id"])
    op.create_index("ix_receita_mo_etapas_receita", "receita_mo_etapas", ["receita_id"])
    op.create_index("ix_produto_massas_produto", "produto_massas", ["produto_id"])
    op.create_index("ix_produto_massas_receita", "produto_massas", ["receita_id"])
    op.create_index("ix_produto_recheios_produto", "produto_recheios", ["produto_id"])
    op.create_index("ix_produto_recheios_receita", "produto_recheios", ["receita_id"])
    op.create_index("ix_produto_ingredientes_produto", "produto_ingredientes", ["produto_id"])
    op.create_index("ix_produto_embalagens_produto", "produto_embalagens", ["produto_id"])
    op.create_index("ix_produto_mo_montagem_produto", "produto_mo_montagem", ["produto_id"])
    op.create_index("ix_produto_precos_produto", "produto_precos", ["produto_id"])
    op.create_index("ix_canais_user", "canais", ["user_id"])
    op.create_index("ix_custos_fixos_user", "custos_fixos", ["user_id"])
    op.create_index("ix_colaboradores_user", "colaboradores", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_colaboradores_user", "colaboradores")
    op.drop_index("ix_custos_fixos_user", "custos_fixos")
    op.drop_index("ix_canais_user", "canais")
    op.drop_index("ix_produto_precos_produto", "produto_precos")
    op.drop_index("ix_produto_mo_montagem_produto", "produto_mo_montagem")
    op.drop_index("ix_produto_embalagens_produto", "produto_embalagens")
    op.drop_index("ix_produto_ingredientes_produto", "produto_ingredientes")
    op.drop_index("ix_produto_recheios_receita", "produto_recheios")
    op.drop_index("ix_produto_recheios_produto", "produto_recheios")
    op.drop_index("ix_produto_massas_receita", "produto_massas")
    op.drop_index("ix_produto_massas_produto", "produto_massas")
    op.drop_index("ix_receita_mo_etapas_receita", "receita_mo_etapas")
    op.drop_index("ix_receita_ingredientes_ingrediente", "receita_ingredientes")
    op.drop_index("ix_receita_ingredientes_receita", "receita_ingredientes")
    op.drop_index("ix_embalagem_precos_embalagem", "embalagem_precos")
    op.drop_index("ix_ingrediente_precos_ingrediente", "ingrediente_precos")
    op.drop_constraint("uq_produto_precos_produto_canal", "produto_precos", type_="unique")
