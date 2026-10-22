"""Initial database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-22 00:00:00.000000

Reflects:
  - PlaceModel (places)
  - PlaceAliasModel (place_aliases)
  - SourceModel (sources)
  - ObservationModel (observations)
  - ImportBatchModel (import_batches)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. places
    op.create_table(
        "places",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("place_type", sa.String(length=32), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("resolution_method", sa.String(length=64), nullable=True),
        sa.Column("geometry_available", sa.Boolean(), nullable=False),
        sa.Column("search_text", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["places.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_places_created_at", "places", ["created_at"], unique=False)
    op.create_index("ix_places_name_lower", "places", ["canonical_name"], unique=False)
    op.create_index("ix_places_parent_id", "places", ["parent_id"], unique=False)
    op.create_index("ix_places_place_type", "places", ["place_type"], unique=False)
    op.create_index("ix_places_search_text", "places", ["search_text"], unique=False)

    # 2. sources
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("licence", sa.String(length=255), nullable=True),
        sa.Column("access_mode", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("last_success", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_created_at", "sources", ["created_at"], unique=False)

    # 3. import_batches
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("imported_by", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_known_good", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_domain", "import_batches", ["domain"], unique=False)
    op.create_index("ix_import_batches_last_known_good", "import_batches", ["last_known_good"], unique=False)
    op.create_index("ix_import_batches_status", "import_batches", ["status"], unique=False)

    # 4. place_aliases
    op.create_table(
        "place_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("place_id", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("alias_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("place_id", "alias", "alias_type", name="uq_place_alias"),
    )
    op.create_index("ix_place_aliases_place_id", "place_aliases", ["place_id"], unique=False)

    # 5. observations
    op.create_table(
        "observations",
        sa.Column("record_type", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("place_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("reference_period_start", sa.Date(), nullable=True),
        sa.Column("reference_period_end", sa.Date(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("licence", sa.String(length=255), nullable=True),
        sa.Column("transformation_version", sa.String(length=64), nullable=True),
        sa.Column("quality_status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("health_category", sa.String(length=32), nullable=True),
        sa.Column("issuing_authority", sa.String(length=255), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("affected_geography_level", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=64), nullable=True),
        sa.Column("disease_code", sa.String(length=64), nullable=True),
        sa.Column("prevention_link", sa.Text(), nullable=True),
        sa.Column("prevention_link_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_observations_created_at", "observations", ["created_at"], unique=False)
    op.create_index("ix_observations_domain", "observations", ["domain"], unique=False)
    op.create_index("ix_observations_field_name", "observations", ["field_name"], unique=False)
    op.create_index("ix_observations_field_place", "observations", ["field_name", "place_id"], unique=False)
    op.create_index("ix_observations_health_category", "observations", ["health_category"], unique=False)
    op.create_index("ix_observations_place_category", "observations", ["place_id", "health_category"], unique=False)
    op.create_index("ix_observations_place_domain", "observations", ["place_id", "domain"], unique=False)
    op.create_index("ix_observations_place_id", "observations", ["place_id"], unique=False)
    op.create_index("ix_observations_quality_status", "observations", ["quality_status"], unique=False)
    op.create_index("ix_observations_record_type", "observations", ["record_type"], unique=False)
    op.create_index("ix_observations_source_id", "observations", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_observations_source_id", table_name="observations")
    op.drop_index("ix_observations_record_type", table_name="observations")
    op.drop_index("ix_observations_quality_status", table_name="observations")
    op.drop_index("ix_observations_place_id", table_name="observations")
    op.drop_index("ix_observations_place_domain", table_name="observations")
    op.drop_index("ix_observations_place_category", table_name="observations")
    op.drop_index("ix_observations_health_category", table_name="observations")
    op.drop_index("ix_observations_field_place", table_name="observations")
    op.drop_index("ix_observations_field_name", table_name="observations")
    op.drop_index("ix_observations_domain", table_name="observations")
    op.drop_index("ix_observations_created_at", table_name="observations")
    op.drop_table("observations")

    op.drop_index("ix_place_aliases_place_id", table_name="place_aliases")
    op.drop_table("place_aliases")

    op.drop_index("ix_import_batches_status", table_name="import_batches")
    op.drop_index("ix_import_batches_last_known_good", table_name="import_batches")
    op.drop_index("ix_import_batches_domain", table_name="import_batches")
    op.drop_table("import_batches")

    op.drop_index("ix_sources_created_at", table_name="sources")
    op.drop_table("sources")

    op.drop_index("ix_places_search_text", table_name="places")
    op.drop_index("ix_places_place_type", table_name="places")
    op.drop_index("ix_places_parent_id", table_name="places")
    op.drop_index("ix_places_name_lower", table_name="places")
    op.drop_index("ix_places_created_at", table_name="places")
    op.drop_table("places")
