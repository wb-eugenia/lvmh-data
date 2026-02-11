"""Create opportunity actions table.

Revision ID: 20260211_0003
Revises: 20260211_0002
Create Date: 2026-02-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260211_0003"
down_revision: Union[str, Sequence[str], None] = "20260211_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunity_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("manager_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False, server_default="open"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'planned', 'done')",
            name="ck_opportunity_actions_status_valid",
        ),
        sa.CheckConstraint(
            "action_type IN ('open', 'call', 'schedule', 'assign', 'other')",
            name="ck_opportunity_actions_type_valid",
        ),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_id", name="uq_opportunity_actions_note"),
    )
    op.create_index(op.f("ix_opportunity_actions_id"), "opportunity_actions", ["id"], unique=False)
    op.create_index(op.f("ix_opportunity_actions_manager_id"), "opportunity_actions", ["manager_id"], unique=False)
    op.create_index(op.f("ix_opportunity_actions_note_id"), "opportunity_actions", ["note_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_opportunity_actions_note_id"), table_name="opportunity_actions")
    op.drop_index(op.f("ix_opportunity_actions_manager_id"), table_name="opportunity_actions")
    op.drop_index(op.f("ix_opportunity_actions_id"), table_name="opportunity_actions")
    op.drop_table("opportunity_actions")

