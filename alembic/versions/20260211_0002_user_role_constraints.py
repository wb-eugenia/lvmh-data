"""Enforce valid user roles.

Revision ID: 20260211_0002
Revises: 20260211_0001
Create Date: 2026-02-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260211_0002"
down_revision: Union[str, Sequence[str], None] = "20260211_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize existing roles before enforcing constraints.
    op.execute(
        """
        UPDATE users
        SET role = lower(trim(role))
        WHERE role IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users
        SET role = 'advisor'
        WHERE role IS NULL
           OR trim(role) = ''
           OR role NOT IN ('advisor', 'manager', 'admin')
        """
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_users_role_valid",
            "role IN ('advisor', 'manager', 'admin')",
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role_valid", type_="check")
        batch_op.alter_column(
            "role",
            existing_type=sa.String(),
            nullable=True,
        )
