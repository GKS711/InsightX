"""v6.1: add UniqueConstraint(workspace_id, primary_url) on stores

Revision ID: ed45898ffc55
Revises: 578d92de7851
Create Date: 2026-05-19

Codex pre-freeze review (task 0d309dd01043) flagged that concurrent
POST /api/v5/stores (or bridge-side same-URL inserts) could race to
create duplicate Store rows for the same primary_url within a workspace.

Schema-level fix: add UniqueConstraint(workspace_id, primary_url) so the
DB rejects the second concurrent insert with IntegrityError; route code
catches that and returns 409 instead of 500.

NULL primary_url is allowed and multiple Stores can have NULL
(SQLite/Postgres both treat NULLs as distinct in UNIQUE indexes).

SQLite specific: ALTER TABLE doesn't support adding constraints, so
batch_alter_table copies the table.
"""
from alembic import op


# revision identifiers
revision = "ed45898ffc55"
down_revision = "578d92de7851"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stores", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_stores_workspace_primary_url",
            ["workspace_id", "primary_url"],
        )


def downgrade() -> None:
    with op.batch_alter_table("stores", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_stores_workspace_primary_url", type_="unique"
        )
