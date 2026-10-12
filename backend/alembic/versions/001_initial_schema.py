"""Initial schema.

Creates participants, meals, food items, recommendations, rule executions,
cards/decks/battles and the audit log. Deliberately contains no image table
and no image column: photos are never persisted (see docs/ephemeral-processing.md).

Revision ID: 001
Revises: None
"""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    raise NotImplementedError


def downgrade() -> None:
    raise NotImplementedError
