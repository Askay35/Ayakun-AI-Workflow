"""Allow workflow delete by nulling billing run FKs.

Revision ID: b5c6d7e8f9a0
Revises: a3b4c5d6e7f8
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("usage_records_workflow_run_id_fkey", "usage_records", type_="foreignkey")
    op.create_foreign_key(
        "usage_records_workflow_run_id_fkey",
        "usage_records",
        "workflow_runs",
        ["workflow_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("billing_reservations_workflow_run_id_fkey", "billing_reservations", type_="foreignkey")
    op.create_foreign_key(
        "billing_reservations_workflow_run_id_fkey",
        "billing_reservations",
        "workflow_runs",
        ["workflow_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("billing_reservations_workflow_run_id_fkey", "billing_reservations", type_="foreignkey")
    op.create_foreign_key(
        "billing_reservations_workflow_run_id_fkey",
        "billing_reservations",
        "workflow_runs",
        ["workflow_run_id"],
        ["id"],
    )
    op.drop_constraint("usage_records_workflow_run_id_fkey", "usage_records", type_="foreignkey")
    op.create_foreign_key(
        "usage_records_workflow_run_id_fkey",
        "usage_records",
        "workflow_runs",
        ["workflow_run_id"],
        ["id"],
    )
