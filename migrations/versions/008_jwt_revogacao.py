"""Revogação de JWT: users.token_version + tabela revoked_tokens.

Permite invalidar sessões antes do `exp`:
- `token_version` no User — bumpar (logout-all / troca de senha) derruba TODOS
  os tokens do usuário (o token carrega o `tv` da emissão).
- `revoked_tokens` — denylist por `jti` para logout de um único dispositivo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("revogado_em", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_revoked_tokens_user_id", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    op.drop_column("users", "token_version")
