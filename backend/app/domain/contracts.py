"""Place, source, and observation contract models (Pydantic v2)."""

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, field_validator

from app.domain.common import (
    AccessMode,
    DataStatus,
    GeographyLevel,
    HealthCategory,
    PlaceType,
    VerificationStatus,
)
from enum import Enum


def utcnow() -> datetime:
    """Timezone-aware current time (UTC)."""
    return datetime.now(UTC)


class Place(BaseModel):
    """A resolved geographic entity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64)
    canonical_name: str = Field(min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    place_type: PlaceType
    parent_id: str | None = Field(default=None, max_length=64)
    # (lat, lng)
    coordinates: tuple[float, float] | None = None
    resolution_method: str | None = Field(default=None, max_length=64)
    geometry_available: bool = False

    @field_validator("aliases")
    @classmethod
    def _limit_aliases(cls, value: list[str]) -> list[str]:
        return [alias[:255] for alias in value[:25]]


class AdminHierarchy(BaseModel):
    """Ancestor chain for a place, ordered from immediate parent upward."""

    state: str | None = None
    district: str | None = None
    subdistrict: str | None = None
    village: str | None = None


class Source(BaseModel):
    """A registered, citable data source."""

    id: str = Field(min_length=1, max_length=128)
    publisher: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    url: str | None = None
    licence: str | None = None
    access_mode: AccessMode
    verification_status: VerificationStatus
    last_success: datetime | None = None


class SourceSummary(BaseModel):
    """Compact source attribution attached to a panel or observation."""

    source_id: str
    publisher: str
    name: str
    url: str | None = None
    licence: str | None = None
    reference_period: str | None = None
    retrieved_at: datetime
    verification_status: VerificationStatus


class Observation(BaseModel):
    """A single measured fact with full provenance."""

    field_name: str = Field(min_length=1, max_length=128)
    value: float | str | None
    unit: str | None = Field(default=None, max_length=64)
    place_id: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=128)
    reference_period_start: date | None = None
    reference_period_end: date | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    quality_status: DataStatus
    licence: str | None = None
    notes: str | None = Field(default=None, max_length=1000)
    domain: str | None = None
    source_url: str | None = Field(
        default=None,
        description=(
            "Link to the record the value came from. Part of provenance: without it a "
            "reader cannot check the figure, and the freshness rules cannot tell a "
            "dated source from an undated fixture."
        ),
    )
    # Optional extended metadata for later extended observation types.
    satellite_mission: str | None = Field(default=None, max_length=255)
    resolution_meters: float | None = Field(default=None, description="Nominal spatial resolution of the observation in metres.")
    cloud_cover_percentage: float | None = Field(default=None, description="Scene-level or aggregate cloud fraction where relevant.")
    scene_timestamp: str | None = Field(default=None, description="ISO 8601 timestamp for imagery acquisition.")


class HealthObservation(Observation):
    """Health-domain observation with the mandatory safety fields.

    An official alert additionally requires an issuing authority and an issue
    date; those constraints are enforced by `HealthObservation` validators and
    by the adapter base class.
    """

    health_category: HealthCategory
    issuing_authority: str = Field(min_length=1, max_length=255)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    affected_geography_level: GeographyLevel
    severity: str | None = Field(default=None, max_length=64)
    disease_code: str | None = Field(default=None, max_length=64)
    prevention_link: str | None = None
    prevention_link_date: date | None = None

    @field_validator("issuing_authority")
    @classmethod
    def _strip_authority(cls, value: str) -> str:
        return value.strip()

    def is_expired(self, now: datetime | None = None) -> bool:
        """True when the observation's validity window has passed."""
        if self.valid_until is None:
            return False
        reference = now or utcnow()
        if self.valid_until.tzinfo is None:
            self.valid_until = self.valid_until.replace(tzinfo=UTC)
        return self.valid_until < reference


class HealthObservationView(Observation):
    """Health observation as presented to a reader.

    This is deliberately separate from `HealthObservation`. The ingestion
    contract (`HealthObservation`) requires an issuing authority, because an
    official alert without one is unsafe to publish. This read model allows
    the authority to be absent for categories that legitimately do not have
    one (e.g. general prevention guidance) while still surfacing everything
    the reader needs to judge the information: the category, the issuer, the
    validity window, the affected geography, and whether the alert has
    expired.
    """

    health_category: HealthCategory
    issuing_authority: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    affected_geography_level: GeographyLevel | None = None
    severity: str | None = None
    disease_code: str | None = None
    prevention_link: str | None = None
    prevention_link_date: date | None = None
    expired: bool = False

    def compute_expiry(self, now: datetime | None = None) -> bool:
        """Set `expired` from the validity window and return it."""
        reference = now or utcnow()
        if self.valid_until is None:
            self.expired = False
            return False
        end = self.valid_until
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        self.expired = end < reference
        return self.expired


class PanelResponse(BaseModel):
    """An independently-loaded profile panel.

    A single failing provider must not break the whole profile, so every panel
    carries its own status and optional error.
    """

    domain: str
    status: DataStatus
    # `SerializeAsAny` keeps the concrete health fields (category, issuer,
    # expiry) in the JSON payload. A plain `list[Observation]` would silently
    # drop them, which would strip exactly the context a reader needs to
    # judge a health alert.
    observations: Sequence[SerializeAsAny[Observation]] = Field(default_factory=list)
    sources: list[SourceSummary] = Field(default_factory=list)
    last_updated: datetime | None = None
    coverage_note: str | None = None
    data_gaps: list[str] = Field(default_factory=list)
    error: str | None = None


class PlaceProfile(BaseModel):
    """Aggregated profile for a place."""

    place: Place
    hierarchy: AdminHierarchy = Field(default_factory=AdminHierarchy)
    panels: dict[str, PanelResponse] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=utcnow)


class SearchResult(BaseModel):
    """A single place search hit."""

    place: Place
    score: float = 0.0
    match_type: str = Field(default="name", max_length=32)


class SearchResponse(BaseModel):
    """Paginated place search results."""

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0
    degraded: bool = False
    notes: list[str] = Field(default_factory=list)


class DataStatusSummary(BaseModel):
    """Per-domain freshness and provenance summary."""

    domain: str
    status: DataStatus
    last_updated: datetime | None = None
    observation_count: int = 0
    source_count: int = 0
    max_age_days: int | None = None
    age_days: int | None = None
    message: str | None = None


class GetLatestObservationStatus(str, Enum):
    """Status for the latest available observation endpoint."""

    CURRENT = "current"
    RELUCTANT = "reluctant"
    UNAVAILABLE = "unavailable"


class LatestObservationResponse(BaseModel):
    """Response envelope for a single latest-observation endpoint."""

    place: Place
    field_name: str
    status: GetLatestObservationStatus
    observation: Observation | None = None
    unavailable_reason: str | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    coverage_note: str | None = None
    data_gaps: list[str] = Field(default_factory=list)


class LatestObservationResponse(BaseModel):
    """Response envelope for a single latest-observation endpoint."""

    place: Place
    field_name: str
    status: GetLatestObservationStatus
    observation: Observation | None = None
    unavailable_reason: str | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    coverage_note: str | None = None
    data_gaps: list[str] = Field(default_factory=list)


class ApiError(BaseModel):
    """Uniform error envelope returned by the API."""

    code: str
    message: str
    status: int
    request_id: str | None = None
    details: Any | None = None


class GetLatestObservationStatus(str, Enum):
    """Status for the latest available observation endpoint."""

    CURRENT = "current"
    RELUCTANT = "reluctant"
    UNAVAILABLE = "unavailable"


class ReverseGeocodeResponse(BaseModel):
    """Result of reverse geocoding a coordinate pair.

    `inside_coverage` is the field a client must use before showing a place
    profile for a pin. False means the pin fell outside every supported
    boundary and `place` is only the *nearest* supported boundary, provided
    as a reference; its statistics do not describe the pinned point.
    """

    place: Place
    hierarchy: AdminHierarchy
    match_type: str = Field(default="enclosing", description="'enclosing' if inside polygon boundary, 'nearest' if closest centroid")
    distance_km: float = 0.0
    latitude: float
    longitude: float
    inside_coverage: bool = Field(
        default=True,
        description=(
            "True only when the point is enclosed by a supported boundary. "
            "False means `place` is a nearest-boundary reference, not the "
            "administrative unit containing the point."
        ),
    )
    coverage_note: str | None = Field(
        default=None,
        description="Plain-language statement of what the match does and does not mean",
    )

