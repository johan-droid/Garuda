"""Reusable dataset builders for the API tests.

Kept in one place so every test module seeds the database the same way, and
so the shape of the data is described once.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.entities import ObservationModel, PlaceAliasModel, PlaceModel, SourceModel


def seed_dataset(session: Session) -> None:
    """Insert a small, realistic dataset: two places, one source, observations."""
    odisha = PlaceModel(
        id="IN-OD",
        canonical_name="Odisha",
        place_type="state",
        parent_id=None,
        latitude=20.9517,
        longitude=85.0985,
        resolution_method="admin_codes",
        geometry_available=True,
        search_text="odisha",
    )
    bhubaneswar = PlaceModel(
        id="IN-OD-29",
        canonical_name="Bhubaneswar",
        place_type="district",
        parent_id="IN-OD",
        latitude=20.2961,
        longitude=85.8245,
        resolution_method="admin_codes",
        geometry_available=True,
        search_text="bhubaneswar",
    )
    source = SourceModel(
        id="src-mohfw",
        publisher="Ministry of Health & Family Welfare",
        name="Health & Family Welfare Statistics",
        url="https://example.invalid/mohfw",
        licence="CC-BY-4.0",
        access_mode="api",
        verification_status="verified",
        last_success=datetime.now(UTC) - timedelta(days=1),
    )
    alias = PlaceAliasModel(place_id="IN-OD", alias="Orissa", alias_type="name")
    session.add_all([odisha, bhubaneswar, source])
    # The alias row has a foreign key onto the place, so the places must be
    # written before it.
    session.flush()
    session.add(alias)

    now = datetime.now(UTC)
    session.add_all(
        [
            ObservationModel(
                field_name="population",
                value_numeric=45000000.0,
                unit="persons",
                place_id="IN-OD",
                source_id="src-mohfw",
                domain="demographics",
                source_url="https://example.invalid/mohfw/pop",
                publisher="Ministry of Health & Family Welfare",
                retrieved_at=now - timedelta(days=30),
                licence="CC-BY-4.0",
                transformation_version="import-v1",
                quality_status="current",
            ),
            ObservationModel(
                field_name="dengue_cases",
                value_numeric=128.0,
                unit="cases",
                place_id="IN-OD-29",
                source_id="src-mohfw",
                domain="health",
                source_url="https://example.invalid/mohfw/dengue",
                publisher="Ministry of Health & Family Welfare",
                retrieved_at=now - timedelta(days=2),
                licence="CC-BY-4.0",
                transformation_version="import-v1",
                quality_status="current",
                health_category="routine_surveillance",
                issuing_authority="Directorate of Public Health, Odisha",
                affected_geography_level="district",
            ),
            ObservationModel(
                field_name="cholera_alert",
                value_text="Avoid contaminated water",
                place_id="IN-OD-29",
                source_id="src-mohfw",
                domain="health",
                source_url="https://example.invalid/mohfw/cholera",
                publisher="Ministry of Health & Family Welfare",
                retrieved_at=now - timedelta(days=1),
                licence="CC-BY-4.0",
                transformation_version="import-v1",
                quality_status="current",
                health_category="official_alert",
                issuing_authority="Directorate of Public Health, Odisha",
                affected_geography_level="district",
                severity="moderate",
                valid_from=now - timedelta(days=1),
                valid_until=now + timedelta(days=6),
            ),
        ]
    )
    session.commit()
