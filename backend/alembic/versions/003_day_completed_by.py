"""day completed by

Στάδιο 2 των κενών backend ↔ mockups (docs/decisions/2026-11-12_backend_gaps.txt, Απόφαση 15):
day_status.completed_by = child | auto (NULL όσο η ημέρα δεν είναι πλήρης). Οι ημέρες που ήταν ήδη πλήρεις τις είχε
δηλώσει το παιδί (δεν υπήρχε άλλος τρόπος), άρα γίνονται «child».
Το autogenerate δεν βλέπει CHECK constraints: το constraint προστέθηκε με το χέρι.

Revision ID: 003
Revises: 002
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('day_status', schema=None) as batch_op:
        batch_op.add_column(sa.Column('completed_by', sa.String(length=8), nullable=True))
        batch_op.create_check_constraint(batch_op.f('ck_day_status_completed_by'), "completed_by IN ('child', 'auto')")
    day_status = sa.table('day_status', sa.column('completed', sa.Boolean()), sa.column('completed_by', sa.String()))
    op.execute(day_status.update().where(day_status.c.completed.is_(True)).values(completed_by='child'))


def downgrade() -> None:
    with op.batch_alter_table('day_status', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('ck_day_status_completed_by'), type_='check')
        batch_op.drop_column('completed_by')
