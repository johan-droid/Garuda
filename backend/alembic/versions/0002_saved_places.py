"""Saved places: server-side bookmarks, scoped by an opaque client id.

Revision ID: 0002_saved_places
Revises: 0001_initial_schema
Create Date: 2026-10-25 00:00:00.000000

Reflects:
  - SavedPlaceModel (saved_places)

The composite primary key `(owner_id, place_id)` is the idempotency key: it
makes "save the same place twice" a single row by construction, rather than
relying on the application to check before inserting. Nothing here references
`places.id` - a bookmark must survive the place row it points at being
re-imported or renamed, and it stores the whole place payload for exactly that
reason.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_saved_places"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_places",
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("place_id", sa.String(length=64), nullable=False),
        sa.Column("place_data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "place_id"),
    )
    # The list endpoint orders by created_at and always filters by owner_id,
    # so this index serves both the ordering and the per-visitor scoping.
    op.create_index("ix_saved_places_created_at", "saved_places", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_saved_places_created_at", table_name="saved_places")
    op.drop_table("saved_places")
