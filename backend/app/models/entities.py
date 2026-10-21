"""SQLAlchemy ORM models.

The schema mirrors the provenance contract: every observation points at a
registered source and a place, and carries its own reference period and
quality status so staleness can be computed from data alone.
"""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    """Timezone-aware current time (UTC)."""
    return datetime.now(UTC)


class TimestampMixin:
    """Audit timestamps for every persisted record."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PlaceModel(Base, TimestampMixin):
    """A resolved geographic entity."""

    __tablename__ = "places"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    place_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("places.id", ondelete="SET NULL"), nullable=True, index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geometry_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    search_text: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    parent: Mapped["PlaceModel | None"] = relationship(remote_side="PlaceModel.id")
    children: Mapped[list["PlaceModel"]] = relationship(back_populates="parent")

    __table_args__ = (
        Index("ix_places_name_lower", "canonical_name"),
        Index("ix_places_search_text", "search_text"),
    )


class PlaceAliasModel(Base):
    """Alternative names/identifiers for a place (e.g. transliterations)."""

    __tablename__ = "place_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    place_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(32), default="name", nullable=False)

    __table_args__ = (UniqueConstraint("place_id", "alias", "alias_type", name="uq_place_alias"),)


class SourceModel(Base, TimestampMixin):
    """A registered data source in the source register."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    licence: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_mode: Mapped[str] = mapped_column(String(32), default="api", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified", nullable=False)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ObservationModel(Base, TimestampMixin):
    """A single fact with provenance.

    `quality_status` is stored rather than derived so the stored value reflects
    what was known at ingestion time; freshness is recomputed at read time.

    Health-specific columns live in the same table (single-table inheritance)
    so provenance columns are not duplicated and no composite primary key is
    needed. They are nullable for non-health domains.
    """

    __tablename__ = "observations"

    __mapper_args__ = {
        "polymorphic_on": "record_type",
        "polymorphic_identity": "observation",
    }

    record_type: Mapped[str] = mapped_column(String(16), default="observation", nullable=False, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    place_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    licence: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transformation_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(32), default="current", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Health-specific columns (nullable outside the health domain).
    health_category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    affected_geography_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    disease_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prevention_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    prevention_link_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    source: Mapped[SourceModel] = relationship(lazy="joined")
    place: Mapped[PlaceModel] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_observations_place_domain", "place_id", "domain"),
        Index("ix_observations_field_place", "field_name", "place_id"),
        Index("ix_observations_place_category", "place_id", "health_category"),
    )


class HealthObservationModel(ObservationModel):
    """Health observation with the mandatory safety fields.

    The health columns are constrained at the validation layer (see
    `app.domain.contracts.HealthObservation`) and in the adapter base class,
    so an official alert always names an issuing authority.
    """

    __mapper_args__ = {"polymorphic_identity": "health"}


class ImportBatchModel(Base):
    """Tracks a dataset import so it can be audited and rolled back.

    `last_known_good` marks the batch whose data is currently served; a failed
    or partial import never replaces it.
    """

    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_known_good: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


