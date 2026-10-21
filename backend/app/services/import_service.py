"""Atomic dataset import with last-known-good semantics.

Guarantees:

  * The whole batch is applied in a single transaction. A failure part-way
    through rolls back everything, so the database never holds a half-imported
    dataset.
  * The batch is only marked `last_known_good` after it commits successfully.
    If a later import fails, the previous good dataset keeps serving.
  * Rows are validated *before* the transaction opens, so invalid data is
    rejected without touching the database.
  * The payload size and row count are bounded to prevent a runaway import.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.common import DataStatus, GeographyLevel, HealthCategory
from app.models.entities import (
    ImportBatchModel,
    ObservationModel,
    PlaceAliasModel,
    PlaceModel,
    SourceModel,
)

logger = get_logger("garuda.import")


class ImportSource(BaseModel):
    """Source metadata supplied with an import batch."""

    id: str = Field(min_length=1, max_length=128)
    publisher: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    licence: str | None = Field(default=None, max_length=255)
    access_mode: str = Field(default="api", max_length=32)
    verification_status: str = Field(default="unverified", max_length=32)


class ImportPlace(BaseModel):
    """A place that observations can be attached to."""

    id: str = Field(min_length=1, max_length=64)
    canonical_name: str = Field(min_length=1, max_length=255)
    place_type: str = Field(min_length=1, max_length=32)
    parent_id: str | None = Field(default=None, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    resolution_method: str | None = Field(default=None, max_length=64)
    geometry_available: bool = False
    aliases: list[str] = Field(default_factory=list)

    @field_validator("place_type")
    @classmethod
    def _known_place_type(cls, value: str) -> str:
        allowed = {"state", "district", "subdistrict", "village", "point"}
        if value not in allowed:
            raise ValueError(f"place_type must be one of {sorted(allowed)}")
        return value


class ImportObservation(BaseModel):
    """A single observation row in an import batch."""

    field_name: str = Field(min_length=1, max_length=128)
    value: float | str | None = None
    unit: str | None = Field(default=None, max_length=64)
    place_id: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=128)
    domain: str = Field(min_length=1, max_length=64)
    reference_period_start: str | None = None
    reference_period_end: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    licence: str | None = Field(default=None, max_length=255)
    quality_status: str = Field(default="current", max_length=32)
    notes: str | None = Field(default=None, max_length=1000)
    # Health-specific fields.
    health_category: str | None = Field(default=None, max_length=32)
    issuing_authority: str | None = Field(default=None, max_length=255)
    affected_geography_level: str | None = Field(default=None, max_length=32)
    severity: str | None = Field(default=None, max_length=64)
    disease_code: str | None = Field(default=None, max_length=64)
    prevention_link: str | None = Field(default=None, max_length=2000)
    prevention_link_date: str | None = Field(default=None, max_length=32)
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @field_validator("quality_status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        allowed = {status.value for status in DataStatus}
        if value not in allowed:
            raise ValueError(f"quality_status must be one of {sorted(allowed)}")
        return value

    @field_validator("health_category")
    @classmethod
    def _known_health_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {category.value for category in HealthCategory}
        if value not in allowed:
            raise ValueError(f"health_category must be one of {sorted(allowed)}")
        return value

    @field_validator("affected_geography_level")
    @classmethod
    def _known_geography_level(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {level.value for level in GeographyLevel}
        if value not in allowed:
            raise ValueError(f"affected_geography_level must be one of {sorted(allowed)}")
        return value


class ImportBatch(BaseModel):
    """A complete import request."""

    domain: str = Field(min_length=1, max_length=64)
    source: ImportSource
    places: list[ImportPlace] = Field(default_factory=list)
    observations: list[ImportObservation] = Field(default_factory=list)
    replace_existing: bool = Field(
        default=True,
        description="Replace the existing rows for this domain and source atomically.",
    )
    imported_by: str | None = Field(default=None, max_length=128)


class ImportResult(BaseModel):
    """Outcome of an import attempt."""

    batch_id: str
    domain: str
    status: str
    places_written: int = 0
    observations_written: int = 0
    last_known_good: bool = False
    message: str | None = None


def _parse_date(value: str | None) -> Any:
    """Parse an ISO date string, returning None when absent or invalid."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _validate_batch(session: Session, batch: ImportBatch) -> None:
    """Validate a batch before the transaction opens.

    Raises `ValueError` with a clear message so the caller can report which
    row is wrong without exposing internals.
    """
    if len(batch.observations) > settings.INGEST_MAX_ROWS:
        raise ValueError(
            f"Import exceeds the maximum of {settings.INGEST_MAX_ROWS} rows per batch."
        )
    if len(batch.places) > settings.INGEST_MAX_ROWS:
        raise ValueError(
            f"Import exceeds the maximum of {settings.INGEST_MAX_ROWS} places per batch."
        )

    declared_place_ids = {place.id for place in batch.places}
    source_ids = {batch.source.id}

    # A place may be referenced by an observation without being re-declared in
    # the batch, as long as it already exists in the database. Only a place
    # that is neither declared nor already present is an error.
    def _place_exists(place_id: str) -> bool:
        if place_id in declared_place_ids:
            return True
        return session.get(PlaceModel, place_id) is not None

    for index, observation in enumerate(batch.observations):
        if observation.source_id not in source_ids:
            raise ValueError(
                f"Observation {index} references source '{observation.source_id}', "
                "which is not declared in this batch."
            )
        if not _place_exists(observation.place_id):
            raise ValueError(
                f"Observation {index} references place '{observation.place_id}', "
                "which is neither declared in this batch nor present in the database."
            )
        if observation.domain != batch.domain:
            raise ValueError(
                f"Observation {index} declares domain '{observation.domain}', "
                f"but the batch domain is '{batch.domain}'."
            )
        if observation.health_category == "official_alert" and not observation.issuing_authority:
            raise ValueError(
                f"Observation {index} is an official alert and must name an issuing authority."
            )
        if (
            observation.health_category == "official_alert"
            and observation.affected_geography_level is None
        ):
            raise ValueError(
                f"Observation {index} is an official alert and must state the affected "
                "geographic level."
            )
        if (
            observation.valid_from is not None
            and observation.valid_until is not None
            and observation.valid_until < observation.valid_from
        ):
            raise ValueError(
                f"Observation {index} has a validity window that ends before it starts."
            )


def import_batch(session: Session, batch: ImportBatch) -> ImportResult:
    """Apply an import batch atomically.

    On any error the transaction is rolled back and the previously imported
    data remains in place and in service.
    """
    _validate_batch(session, batch)

    batch_id = f"imp_{uuid.uuid4().hex[:16]}"
    now = datetime.now(UTC)

    existing_good = session.scalars(
        select(ImportBatchModel).where(
            ImportBatchModel.domain == batch.domain,
            ImportBatchModel.last_known_good.is_(True),
        )
    ).first()

    import_record = ImportBatchModel(
        id=batch_id,
        domain=batch.domain,
        source_id=batch.source.id,
        status="pending",
        row_count=len(batch.observations),
        imported_by=batch.imported_by,
        last_known_good=False,
        started_at=now,
    )
    session.add(import_record)
    session.flush()

    try:
        _write_source(session, batch, now)
        _write_places(session, batch)
        _write_observations(session, batch, now)
        _promote_to_last_known_good(session, import_record, existing_good, batch)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(
            "import_failed",
            extra={
                "extra_fields": {
                    "batch_id": batch_id,
                    "domain": batch.domain,
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise

    # The cached search index may now be out of date.
    from app.services.cache import get_cache

    get_cache().invalidate_prefix("place_lookup")

    logger.info(
        "import_completed",
        extra={
            "extra_fields": {
                "batch_id": batch_id,
                "domain": batch.domain,
                "places": len(batch.places),
                "observations": len(batch.observations),
            }
        },
    )

    return ImportResult(
        batch_id=batch_id,
        domain=batch.domain,
        status="completed",
        places_written=len(batch.places),
        observations_written=len(batch.observations),
        last_known_good=True,
        message="Import applied successfully.",
    )


def _write_source(session: Session, batch: ImportBatch, now: datetime) -> None:
    """Create or refresh the source register entry."""
    source_row = session.get(SourceModel, batch.source.id)
    if source_row is None:
        source_row = SourceModel(
            id=batch.source.id,
            publisher=batch.source.publisher,
            name=batch.source.name,
            url=batch.source.url,
            licence=batch.source.licence,
            access_mode=batch.source.access_mode,
            verification_status=batch.source.verification_status,
        )
        session.add(source_row)
    else:
        source_row.publisher = batch.source.publisher
        source_row.name = batch.source.name
        source_row.url = batch.source.url
        source_row.licence = batch.source.licence
        source_row.access_mode = batch.source.access_mode
        source_row.verification_status = batch.source.verification_status
        source_row.last_success = now
    session.flush()


def _write_places(session: Session, batch: ImportBatch) -> None:
    """Create or refresh the places referenced by the batch."""
    for place in batch.places:
        search_text = " ".join([place.canonical_name, *place.aliases]).lower()
        place_row = session.get(PlaceModel, place.id)
        if place_row is None:
            place_row = PlaceModel(
                id=place.id,
                canonical_name=place.canonical_name,
                place_type=place.place_type,
                parent_id=place.parent_id,
                latitude=place.latitude,
                longitude=place.longitude,
                resolution_method=place.resolution_method,
                geometry_available=place.geometry_available,
                search_text=search_text,
            )
            session.add(place_row)
        else:
            place_row.canonical_name = place.canonical_name
            place_row.place_type = place.place_type
            place_row.parent_id = place.parent_id
            place_row.latitude = place.latitude
            place_row.longitude = place.longitude
            place_row.resolution_method = place.resolution_method
            place_row.geometry_available = place.geometry_available
            place_row.search_text = search_text
        # The alias rows have a foreign key onto the place, so they can only
        # be written once the place itself has been flushed.
        session.flush()
        _sync_aliases(session, place_row, place.aliases)
    session.flush()


def _sync_aliases(session: Session, place_row: PlaceModel, aliases: list[str]) -> None:
    """Make the stored alias rows match the imported alias list exactly.

    The alias table is the record of a place's alternative names, so it is
    replaced wholesale rather than merged: an alias that has disappeared from
    the source must not linger in the register.
    """
    wanted = {alias.strip()[:255] for alias in aliases if alias and alias.strip()}

    existing = {
        row.alias: row
        for row in session.scalars(
            select(PlaceAliasModel).where(PlaceAliasModel.place_id == place_row.id)
        )
    }

    for alias, row in existing.items():
        if alias not in wanted:
            session.delete(row)

    for alias in wanted:
        if alias not in existing:
            session.add(
                PlaceAliasModel(
                    place_id=place_row.id,
                    alias=alias,
                    alias_type="name",
                )
            )


def _write_observations(session: Session, batch: ImportBatch, now: datetime) -> None:
    """Replace the domain's observations for this source and write the new rows."""
    if batch.replace_existing:
        session.execute(
            delete(ObservationModel).where(
                ObservationModel.domain == batch.domain,
                ObservationModel.source_id == batch.source.id,
            )
        )

    for observation in batch.observations:
        value_numeric: float | None = None
        value_text: str | None = None
        if isinstance(observation.value, (int, float)) and not isinstance(observation.value, bool):
            value_numeric = float(observation.value)
        elif observation.value is not None:
            value_text = str(observation.value)

        session.add(
            ObservationModel(
                field_name=observation.field_name,
                value_numeric=value_numeric,
                value_text=value_text,
                unit=observation.unit,
                place_id=observation.place_id,
                source_id=observation.source_id,
                domain=observation.domain,
                publisher=batch.source.publisher,
                reference_period_start=_parse_date(observation.reference_period_start),
                reference_period_end=_parse_date(observation.reference_period_end),
                published_at=observation.published_at,
                retrieved_at=observation.retrieved_at or now,
                licence=observation.licence or batch.source.licence,
                transformation_version="import-v1",
                quality_status=observation.quality_status,
                notes=observation.notes,
                health_category=observation.health_category,
                issuing_authority=observation.issuing_authority,
                affected_geography_level=observation.affected_geography_level,
                severity=observation.severity,
                disease_code=observation.disease_code,
                prevention_link=observation.prevention_link,
                prevention_link_date=_parse_date(observation.prevention_link_date),
                valid_from=observation.valid_from,
                valid_until=observation.valid_until,
            )
        )


def _promote_to_last_known_good(
    session: Session,
    import_record: ImportBatchModel,
    existing_good: ImportBatchModel | None,
    batch: ImportBatch,
) -> None:
    """Mark the new batch as the served dataset.

    The previous good batch is demoted in the same transaction, so there is
    never a moment with two "good" batches or with none.
    """
    if existing_good is not None and existing_good.id != import_record.id:
        session.execute(
            update(ImportBatchModel)
            .where(ImportBatchModel.id == existing_good.id)
            .values(last_known_good=False)
        )

    import_record.status = "completed"
    import_record.observation_count = len(batch.observations)
    import_record.last_known_good = True
    import_record.completed_at = datetime.now(UTC)


def list_batches(session: Session, limit: int = 50) -> list[dict[str, Any]]:
    """List recent import batches, newest first."""
    rows = session.scalars(
        select(ImportBatchModel)
        .order_by(ImportBatchModel.started_at.desc())
        .limit(max(1, min(limit, settings.MAX_PAGE_SIZE)))
    )
    return [
        {
            "batch_id": row.id,
            "domain": row.domain,
            "source_id": row.source_id,
            "status": row.status,
            "row_count": row.row_count,
            "observation_count": row.observation_count,
            "last_known_good": row.last_known_good,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
        for row in rows
    ]

