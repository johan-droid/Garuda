"""Server-side bookmark for a place.

A visitor's bookmark is deliberately not kept in the browser: this pilot runs
on shared phones, and browser storage would show the next person to pick the
device up which places were looked at. What is stored here is only what was
pinned, under an opaque id the client itself generated - no account, no
cookie, no profile. Dropping the row is the whole "forget me" this feature
needs.

The primary key doubles as the idempotency key: `(owner_id, place_id)` is
unique by construction, so saving the same place twice cannot make two rows.
"""

from datetime import UTC, datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SavedPlaceModel(Base):
    """One place, pinned by one visitor."""

    __tablename__ = "saved_places"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # The whole Place as the client sent it. The bookmark chip needs the name
    # and the map needs the coordinates, and after a reload neither is
    # derivable from an id alone - the client that still holds the object is
    # the only place they came from.
    place_data: Mapped[str] = mapped_column(Text, nullable=False)
    # Server-side, from the database clock. The list is ordered by this, and
    # a client-supplied timestamp would let a visitor reorder someone else's
    # view of their own bookmarks.
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
