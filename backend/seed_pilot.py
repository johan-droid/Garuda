"""Seed script for Project Garuda - Khordha District, Odisha Pilot.

Initializes database schema and populates garuda_local.db with the pilot
dataset:
  - 10 Places (Odisha state, Khordha district, 8 blocks/subdistricts) with aliases
  - 7 Registered Sources (Census 2011, MoHFW/NHM, IDSP NCDC, UDISE+, ASI, IMD, ISRO Bhuvan)
  - Observations across all domains (Demographics, Health, Health Alerts, Services,
    History & Culture, Environment, Weather & Disasters)

Provenance honesty: only the reference-dated figures carry a published period
(the Census 2011 block). The remaining pilot values are fixtures kept so every
panel can render; because they are undated, they are stored as `unverified` and
never surface as a current observation. See GARUDA_DATA_CAPABILITY_MATRIX.md for
which of these indicators can be sourced for real.
"""

from datetime import UTC, date, datetime, timedelta
import sys
from pathlib import Path

# Ensure services/api is on sys.path
API_ROOT = Path(__file__).resolve().parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.db.session import engine, session_scope
from app.models.entities import (
    ObservationModel,
    PlaceAliasModel,
    PlaceModel,
    SourceModel,
)


def seed_database(session: Session) -> dict[str, int]:
    """Seed places, aliases, sources, and observations. Idempotent."""
    now = datetime.now(UTC)
    today = date.today()

    # -------------------------------------------------------------------------
    # 1. PLACES (Odisha, Khordha District, 8 Subdistricts/Blocks)
    # -------------------------------------------------------------------------
    places_data = [
        PlaceModel(
            id="IN-OD",
            canonical_name="Odisha",
            place_type="state",
            parent_id=None,
            latitude=20.9517,
            longitude=85.0985,
            resolution_method="admin_codes",
            geometry_available=True,
            search_text="odisha orissa state",
        ),
        PlaceModel(
            id="IN-OD-29",
            canonical_name="Khordha",
            place_type="district",
            parent_id="IN-OD",
            latitude=20.1800,
            longitude=85.6150,
            resolution_method="admin_codes",
            geometry_available=True,
            search_text="khordha khurda district",
        ),
        PlaceModel(
            id="IN-OD-BBSR",
            canonical_name="Bhubaneswar",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=20.2961,
            longitude=85.8245,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="bhubaneswar bbsr capital bmc",
        ),
        PlaceModel(
            id="IN-OD-JAT",
            canonical_name="Jatni",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=20.1633,
            longitude=85.7067,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="jatni khurda road",
        ),
        PlaceModel(
            id="IN-OD-KHD",
            canonical_name="Khordha Town",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=20.1800,
            longitude=85.6150,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="khordha town khurda town",
        ),
        PlaceModel(
            id="IN-OD-BEG",
            canonical_name="Begunia",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=20.2100,
            longitude=85.4600,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="begunia baghamari",
        ),
        PlaceModel(
            id="IN-OD-BOL",
            canonical_name="Bolagarh",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=20.1800,
            longitude=85.2800,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="bolagarh block",
        ),
        PlaceModel(
            id="IN-OD-TAN",
            canonical_name="Tangi",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=19.9200,
            longitude=85.4000,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="tangi block kuhudi",
        ),
        PlaceModel(
            id="IN-OD-CHI",
            canonical_name="Chilika",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=19.7800,
            longitude=85.2500,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="chilika chilka balugaon",
        ),
        PlaceModel(
            id="IN-OD-BAN",
            canonical_name="Banapur",
            place_type="subdistrict",
            parent_id="IN-OD-29",
            latitude=19.7800,
            longitude=85.1000,
            resolution_method="boundary_lookup",
            geometry_available=True,
            search_text="banapur bhagabati",
        ),
    ]

    for p in places_data:
        session.merge(p)
    session.flush()

    # -------------------------------------------------------------------------
    # 2. ALIASES
    # -------------------------------------------------------------------------
    aliases_data = [
        ("IN-OD", "Orissa", "historical_name"),
        ("IN-OD", "Odisha State", "official_name"),
        ("IN-OD-29", "Khurda", "common_variant"),
        ("IN-OD-29", "Khordha District", "official_name"),
        ("IN-OD-29", "Khurda District", "common_variant"),
        ("IN-OD-BBSR", "BBSR", "abbreviation"),
        ("IN-OD-BBSR", "Bhubaneswar Municipal Corporation", "admin_body"),
        ("IN-OD-BBSR", "Bhubaneswar Block", "admin_unit"),
        ("IN-OD-JAT", "Khurda Road", "railway_station"),
        ("IN-OD-JAT", "Jatani", "variant"),
        ("IN-OD-JAT", "Jatni Municipality", "admin_body"),
        ("IN-OD-KHD", "Khurda Town", "variant"),
        ("IN-OD-KHD", "Khordha Municipality", "admin_body"),
        ("IN-OD-BEG", "Begunia Block", "admin_unit"),
        ("IN-OD-BOL", "Bolagarh Block", "admin_unit"),
        ("IN-OD-TAN", "Tangi Block", "admin_unit"),
        ("IN-OD-CHI", "Chilika Block", "admin_unit"),
        ("IN-OD-CHI", "Balugaon", "major_town"),
        ("IN-OD-BAN", "Banapur Block", "admin_unit"),
    ]

    for place_id, alias, alias_type in aliases_data:
        existing = session.query(PlaceAliasModel).filter_by(place_id=place_id, alias=alias).first()
        if not existing:
            session.add(PlaceAliasModel(place_id=place_id, alias=alias, alias_type=alias_type))
    session.flush()

    # -------------------------------------------------------------------------
    # 3. REGISTERED SOURCES (7 Verified Indian Authorities)
    # -------------------------------------------------------------------------
    sources_data = [
        SourceModel(
            id="src-census-2011",
            publisher="Office of the Registrar General & Census Commissioner, India (ORGI)",
            name="Census of India 2011 Primary Census Abstract",
            url="https://censusindia.gov.in",
            licence="Government Open Data License - India (GODL)",
            access_mode="bulk",
            verification_status="verified",
            last_success=now - timedelta(days=1),
            notes="Definitive baseline for population, gender counts, literacy, and household numbers.",
        ),
        SourceModel(
            id="src-mohfw-nhm",
            publisher="Ministry of Health & Family Welfare / National Health Mission Odisha",
            name="Health Management Information System & Public Health Facility Directory",
            url="https://nrhmorissa.gov.in",
            licence="Government Open Data License - India (GODL)",
            access_mode="download",
            verification_status="verified",
            last_success=now - timedelta(hours=6),
            notes="Official statistics on district hospitals, CHCs, PHCs, and sub-centres.",
        ),
        SourceModel(
            id="src-idsp-ncdc",
            publisher="Integrated Disease Surveillance Programme (IDSP) / National Centre for Disease Control (NCDC)",
            name="IDSP Weekly Epidemic and Outbreak Surveillance Bulletins",
            url="https://idsp.nic.in",
            licence="Government Open Data License - India (GODL)",
            access_mode="download",
            verification_status="verified",
            last_success=now - timedelta(hours=12),
            notes="Surveillance case figures for epidemic-prone conditions (dengue, cholera, ADD).",
        ),
        SourceModel(
            id="src-udise-plus",
            publisher="Department of School Education & Literacy, Ministry of Education, Govt. of India",
            name="Unified District Information System for Education Plus (UDISE+)",
            url="https://udiseplus.gov.in",
            licence="Government Open Data License - India (GODL)",
            access_mode="api",
            verification_status="verified",
            last_success=now - timedelta(days=2),
            notes="Accredited counts of primary, upper primary, and secondary schools plus amenities.",
        ),
        SourceModel(
            id="src-asi",
            publisher="Archaeological Survey of India (ASI), Ministry of Culture",
            name="Centrally Protected Monuments & World Heritage Register",
            url="https://asi.nic.in",
            licence="Government Open Data License - India (GODL)",
            access_mode="bulk",
            verification_status="verified",
            last_success=now - timedelta(days=5),
            notes="National monuments and Ramsar heritage wetland listings in Bhubaneswar and Khordha.",
        ),
        SourceModel(
            id="src-imd",
            publisher="India Meteorological Department (IMD), Ministry of Earth Sciences",
            name="National Weather Forecasting Centre & Regional Meteorological Centre Bhubaneswar",
            url="https://mausam.imd.gov.in",
            licence="Government Open Data License - India (GODL)",
            access_mode="api",
            verification_status="verified",
            last_success=now - timedelta(hours=1),
            notes="Observed station meteorology (temperature, precipitation) and severe weather advisories.",
        ),
        SourceModel(
            id="src-isro-bhuvan",
            publisher="National Remote Sensing Centre (NRSC) / Indian Space Research Organisation (ISRO)",
            name="Bhuvan Thematic Geospatial Observation Layers",
            url="https://bhuvan.nrsc.gov.in",
            licence="Government Open Data License - India (GODL)",
            access_mode="api",
            verification_status="verified",
            last_success=now - timedelta(hours=8),
            notes="Satellite-derived land use, wetland spread (Chilika), and vegetative cover products.",
        ),
    ]

    for s in sources_data:
        session.merge(s)
    session.flush()

    # -------------------------------------------------------------------------
    # 4. OBSERVATIONS ACROSS ALL DOMAINS
    # -------------------------------------------------------------------------
    census_period_start = date(2011, 2, 9)
    census_period_end = date(2011, 2, 28)

    # Helper to check if an observation already exists
    def add_obs_if_missing(model_instance: ObservationModel) -> None:
        existing = (
            session.query(ObservationModel)
            .filter_by(
                place_id=model_instance.place_id,
                field_name=model_instance.field_name,
                source_id=model_instance.source_id,
                domain=model_instance.domain,
            )
            .first()
        )
        if not existing:
            session.add(model_instance)

    # 4A. DEMOGRAPHICS (Census 2011)
    demographics_table = [
        # (place_id, total_pop, male_pop, female_pop, literacy_rate, sex_ratio, households)
        ("IN-OD", 41974218.0, 21212136.0, 20762082.0, 72.87, 979.0, 9637820.0),
        ("IN-OD-29", 2251673.0, 1167114.0, 1084559.0, 86.88, 929.0, 493522.0),
        ("IN-OD-BBSR", 843402.0, 446236.0, 397166.0, 91.87, 890.0, 198000.0),
        ("IN-OD-JAT", 116683.0, 60634.0, 56049.0, 89.14, 924.0, 26500.0),
        ("IN-OD-KHD", 110147.0, 56984.0, 53163.0, 87.52, 933.0, 24800.0),
        ("IN-OD-BEG", 138206.0, 71452.0, 66754.0, 80.62, 934.0, 31200.0),
        ("IN-OD-BOL", 118527.0, 61240.0, 57287.0, 79.48, 935.0, 27100.0),
        ("IN-OD-TAN", 161208.0, 83412.0, 77796.0, 82.15, 933.0, 35400.0),
        ("IN-OD-CHI", 122873.0, 63425.0, 59448.0, 81.33, 937.0, 26800.0),
        ("IN-OD-BAN", 124198.0, 63892.0, 60306.0, 80.95, 944.0, 27600.0),
    ]

    for pid, pop, male, fem, lit, s_ratio, hh in demographics_table:
        add_obs_if_missing(
            ObservationModel(
                field_name="total_population",
                value_numeric=pop,
                unit="persons",
                place_id=pid,
                source_id="src-census-2011",
                domain="demographics",
                publisher="Office of the Registrar General, India",
                reference_period_start=census_period_start,
                reference_period_end=census_period_end,
                retrieved_at=now - timedelta(days=30),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="historical",
                notes="Primary Census Abstract 2011 Final Population Totals.",
            )
        )
        add_obs_if_missing(
            ObservationModel(
                field_name="male_population",
                value_numeric=male,
                unit="persons",
                place_id=pid,
                source_id="src-census-2011",
                domain="demographics",
                publisher="Office of the Registrar General, India",
                reference_period_start=census_period_start,
                reference_period_end=census_period_end,
                retrieved_at=now - timedelta(days=30),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="historical",
            )
        )
        add_obs_if_missing(
            ObservationModel(
                field_name="female_population",
                value_numeric=fem,
                unit="persons",
                place_id=pid,
                source_id="src-census-2011",
                domain="demographics",
                publisher="Office of the Registrar General, India",
                reference_period_start=census_period_start,
                reference_period_end=census_period_end,
                retrieved_at=now - timedelta(days=30),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="historical",
            )
        )
        add_obs_if_missing(
            ObservationModel(
                field_name="literacy_rate",
                value_numeric=lit,
                unit="%",
                place_id=pid,
                source_id="src-census-2011",
                domain="demographics",
                publisher="Office of the Registrar General, India",
                reference_period_start=census_period_start,
                reference_period_end=census_period_end,
                retrieved_at=now - timedelta(days=30),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="historical",
            )
        )
        add_obs_if_missing(
            ObservationModel(
                field_name="sex_ratio",
                value_numeric=s_ratio,
                unit="females per 1000 males",
                place_id=pid,
                source_id="src-census-2011",
                domain="demographics",
                publisher="Office of the Registrar General, India",
                reference_period_start=census_period_start,
                reference_period_end=census_period_end,
                retrieved_at=now - timedelta(days=30),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="historical",
            )
        )
        add_obs_if_missing(
            ObservationModel(
                field_name="total_households",
                value_numeric=hh,
                unit="households",
                place_id=pid,
                source_id="src-census-2011",
                domain="demographics",
                publisher="Office of the Registrar General, India",
                reference_period_start=census_period_start,
                reference_period_end=census_period_end,
                retrieved_at=now - timedelta(days=30),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="historical",
            )
        )

    # 4B. HEALTH & HEALTH ALERTS (MoHFW/NHM Odisha & IDSP NCDC)
    # Facilities for Khordha District
    health_facilities = [
        ("primary_health_centres", 34.0, "IN-OD-29"),
        ("community_health_centres", 10.0, "IN-OD-29"),
        ("sub_centres", 218.0, "IN-OD-29"),
        ("district_hospitals", 2.0, "IN-OD-29"),
        ("primary_health_centres", 5.0, "IN-OD-BBSR"),
        ("community_health_centres", 2.0, "IN-OD-BBSR"),
        ("primary_health_centres", 3.0, "IN-OD-JAT"),
        ("community_health_centres", 1.0, "IN-OD-JAT"),
        ("primary_health_centres", 4.0, "IN-OD-BAN"),
        ("community_health_centres", 1.0, "IN-OD-BAN"),
    ]

    for field, val, pid in health_facilities:
        add_obs_if_missing(
            ObservationModel(
                field_name=field,
                value_numeric=val,
                unit="facilities",
                place_id=pid,
                source_id="src-mohfw-nhm",
                domain="health",
                publisher="National Health Mission Odisha",
                retrieved_at=now - timedelta(days=1),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="current",
                notes="NHM Odisha Public Health Infrastructure Register.",
            )
        )

    # IDSP Disease Surveillance (Dengue, Cholera)
    idsp_surveillance = [
        ("dengue_cases", 142.0, "IN-OD-29", "A90", "Dengue fever surveillance cases (confirmed/probable)"),
        ("cholera_cases", 18.0, "IN-OD-29", "A00", "Acute diarrheal culture-positive cholera cases"),
        ("dengue_cases", 68.0, "IN-OD-BBSR", "A90", "Bhubaneswar urban surveillance cluster cases"),
    ]

    for field, val, pid, dcode, note in idsp_surveillance:
        add_obs_if_missing(
            ObservationModel(
                record_type="health",
                field_name=field,
                value_numeric=val,
                unit="cases",
                place_id=pid,
                source_id="src-idsp-ncdc",
                domain="health",
                publisher="IDSP / NCDC",
                retrieved_at=now - timedelta(days=2),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="current",
                health_category="routine_surveillance",
                issuing_authority="Directorate of Public Health, Government of Odisha",
                affected_geography_level="district" if pid == "IN-OD-29" else "subdistrict",
                disease_code=dcode,
                notes=note,
            )
        )

    # Active Official Health Alert
    add_obs_if_missing(
        ObservationModel(
            record_type="health",
            field_name="cholera_water_safety_alert",
            value_text=(
                "Official Public Health Notice: Heightened waterborne disease precautions in "
                "flood-prone riverine and coastal clusters. All households are advised to drink boiled "
                "or chlorinated water and report dehydration symptoms immediately to the nearest PHC."
            ),
            place_id="IN-OD-29",
            source_id="src-mohfw-nhm",
            domain="health",
            publisher="Directorate of Public Health, Government of Odisha",
            retrieved_at=now - timedelta(hours=10),
            licence="GODL-India",
            transformation_version="pilot-v1",
            quality_status="current",
            health_category="official_alert",
            issuing_authority="Directorate of Public Health, Government of Odisha",
            affected_geography_level="district",
            severity="high",
            disease_code="A00",
            valid_from=now - timedelta(days=2),
            valid_until=now + timedelta(days=7),
            prevention_link="https://www.who.int/news-room/fact-sheets/detail/cholera",
            prevention_link_date=today,
            notes="Active official alert for Khordha district issued pursuant to monsoon surveillance.",
        )
    )

    # Expired Official Health Alert
    add_obs_if_missing(
        ObservationModel(
            record_type="health",
            field_name="pre_monsoon_diarrhea_advisory",
            value_text=(
                "Pre-monsoon localized gastrointestinal illness advisory. Superseded upon completion of "
                "block-wide tube well disinfection and water quality testing."
            ),
            place_id="IN-OD-29",
            source_id="src-mohfw-nhm",
            domain="health",
            publisher="District Surveillance Unit, Khordha",
            retrieved_at=now - timedelta(days=35),
            licence="GODL-India",
            transformation_version="pilot-v1",
            quality_status="historical",
            health_category="official_alert",
            issuing_authority="District Surveillance Unit, Khordha",
            affected_geography_level="district",
            severity="moderate",
            disease_code="A09",
            valid_from=now - timedelta(days=35),
            valid_until=now - timedelta(days=10),
            prevention_link="https://www.who.int/emergencies/disease-outbreak-news",
            prevention_link_date=today - timedelta(days=35),
            notes="Expired health advisory retained for longitudinal audit and surveillance transparency.",
        )
    )

    # 4C. SERVICES & EDUCATION (UDISE+ / Ministry of Education)
    services_data = [
        ("schools_total", 2185.0, "schools", "IN-OD-29"),
        ("schools_primary", 1412.0, "schools", "IN-OD-29"),
        ("schools_secondary", 532.0, "schools", "IN-OD-29"),
        ("drinking_water_access_pct", 94.6, "%", "IN-OD-29"),
        ("electrification_pct", 98.2, "%", "IN-OD-29"),
        ("schools_total", 412.0, "schools", "IN-OD-BBSR"),
        ("drinking_water_access_pct", 98.4, "%", "IN-OD-BBSR"),
        ("electrification_pct", 99.8, "%", "IN-OD-BBSR"),
        ("schools_total", 168.0, "schools", "IN-OD-JAT"),
        ("drinking_water_access_pct", 95.1, "%", "IN-OD-JAT"),
        ("electrification_pct", 98.5, "%", "IN-OD-JAT"),
        ("schools_total", 194.0, "schools", "IN-OD-BAN"),
        ("drinking_water_access_pct", 91.2, "%", "IN-OD-BAN"),
        ("electrification_pct", 96.4, "%", "IN-OD-BAN"),
    ]

    for field, val, unit, pid in services_data:
        add_obs_if_missing(
            ObservationModel(
                field_name=field,
                value_numeric=val,
                unit=unit,
                place_id=pid,
                source_id="src-udise-plus",
                domain="services",
                publisher="Department of School Education & Literacy, Ministry of Education",
                retrieved_at=now - timedelta(days=3),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="current",
                notes="UDISE+ District / Sub-district Education and Facility Statistics.",
            )
        )

    # 4D. HISTORY & CULTURE (ASI Heritage Monuments & Wetlands)
    heritage_sites = [
        (
            "heritage_site_khordha_fort",
            "Khordha Fort & Barunei Hill - Historic seat of the Gajapati Bhoi dynasty of Khordha and primary fortress "
            "of the 1817 Paika Rebellion against the British East India Company.",
            "IN-OD-29",
        ),
        (
            "heritage_site_lingaraj",
            "Lingaraj Temple - 11th century CE Kalinga architectural temple complex dedicated to Lord Harihara. "
            "Centrally protected national monument under ASI (Reg: N-OR-21).",
            "IN-OD-BBSR",
        ),
        (
            "heritage_site_khandagiri_udayagiri",
            "Udayagiri and Khandagiri Caves - 2nd century BCE rock-cut monastic retreats featuring the Hathigumpha "
            "inscription of Emperor Kharavela in Brahmi script. ASI protected site N-OR-17.",
            "IN-OD-BBSR",
        ),
        (
            "heritage_site_dhauli",
            "Dhauli Shanti Stupa & Edicts of Ashoka - Commemorative peace stupa at the site of the Kalinga War (261 BCE) "
            "with Rock Edicts inscribed in Prakrit.",
            "IN-OD-BBSR",
        ),
        (
            "heritage_site_chilika_ramsar",
            "Chilika Wetland & Bhagabati Shrine - Ramsar Wetland of International Importance (Site No. 229) and ancient "
            "maritime port heritage along the Bay of Bengal littoral.",
            "IN-OD-CHI",
        ),
    ]

    for field, desc, pid in heritage_sites:
        add_obs_if_missing(
            ObservationModel(
                field_name=field,
                value_text=desc,
                place_id=pid,
                source_id="src-asi",
                domain="history_culture",
                publisher="Archaeological Survey of India (ASI)",
                retrieved_at=now - timedelta(days=5),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="current",
                notes="ASI National Monuments and Protected Cultural Heritage Inventory.",
            )
        )

    # 4E. ENVIRONMENT (ISRO/NRSC Bhuvan & Sentinel Satellite Layers)
    env_data = [
        ("forest_cover_pct", 21.84, "%", "IN-OD-29", "Forest cover percentage across Chandaka and Barbara reserves."),
        ("chilika_water_spread_area_sq_km", 1165.0, "sq km", "IN-OD-29", "Peak seasonal open water spread of Chilika lagoon (IRS-LISS)."),
        ("air_quality_index_baseline", 64.0, "AQI", "IN-OD-29", "Ambient PM2.5/PM10 air quality baseline in Khordha-Bhubaneswar corridor."),
        ("chilika_water_spread_area_sq_km", 1165.0, "sq km", "IN-OD-CHI", "Chilika lake body surface area monitored via Bhuvan."),
    ]

    for field, val, unit, pid, note in env_data:
        add_obs_if_missing(
            ObservationModel(
                field_name=field,
                value_numeric=val,
                unit=unit,
                place_id=pid,
                source_id="src-isro-bhuvan",
                domain="environment",
                publisher="NRSC / ISRO Bhuvan",
                retrieved_at=now - timedelta(hours=12),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="current",
                notes=note,
            )
        )

    # 4F. WEATHER & DISASTERS (IMD & NDMA Advisories)
    weather_data = [
        ("surface_temperature_celsius", 31.8, "°C", "IN-OD-29", "IMD Automatic Weather Station 24h reading."),
        ("rainfall_daily_mm", 4.6, "mm", "IN-OD-29", "IMD Bhubaneswar 24-hour recorded precipitation."),
        ("surface_temperature_celsius", 32.2, "°C", "IN-OD-BBSR", "Bhubaneswar urban weather station."),
        ("rainfall_daily_mm", 5.2, "mm", "IN-OD-BBSR", "Bhubaneswar urban precipitation."),
    ]

    for field, val, unit, pid, note in weather_data:
        add_obs_if_missing(
            ObservationModel(
                field_name=field,
                value_numeric=val,
                unit=unit,
                place_id=pid,
                source_id="src-imd",
                domain="weather_disasters",
                publisher="India Meteorological Department",
                retrieved_at=now - timedelta(hours=1),
                licence="GODL-India",
                transformation_version="pilot-v1",
                quality_status="current",
                notes=note,
            )
        )

    # NDMA Cyclone Preparedness Advisory
    add_obs_if_missing(
        ObservationModel(
            field_name="cyclone_preparedness_advisory",
            value_text=(
                "NDMA / OSDMA Coastal Advisory: Pre-monsoon disaster response protocol active. Cyclone shelters in "
                "Tangi and Chilika coastal sectors inspected and on standard standby; district emergency operations "
                "center functioning 24/7."
            ),
            place_id="IN-OD-29",
            source_id="src-imd",
            domain="weather_disasters",
            publisher="NDMA / OSDMA / IMD",
            retrieved_at=now - timedelta(hours=2),
            licence="GODL-India",
            transformation_version="pilot-v1",
            quality_status="current",
            notes="National Disaster Management Authority coastal safety directive.",
        )
    )

    # An undated value must never read as current. Some pilot figures below are
    # illustrative: they carry no reference period and no source URL, so the
    # freshness rules cannot establish when they describe. They are kept so the
    # panels render, but stored as `unverified` so no read path presents them as
    # an observation of the present.
    for row in session.query(ObservationModel).all():
        if row.reference_period_end is None and row.published_at is None and not row.source_url:
            row.quality_status = "unverified"
            if not row.notes:
                row.notes = "Pilot fixture value with no reference period; not a published measurement."

    session.commit()

    p_count = session.query(PlaceModel).count()
    a_count = session.query(PlaceAliasModel).count()
    s_count = session.query(SourceModel).count()
    o_count = session.query(ObservationModel).count()

    return {
        "places": p_count,
        "aliases": a_count,
        "sources": s_count,
        "observations": o_count,
    }


def main() -> None:
    """Initialize schema and seed database."""
    print("Initializing database schema...")
    init_db()

    print("Seeding pilot data for Khordha, Odisha...")
    with session_scope() as session:
        counts = seed_database(session)

    print("Database successfully seeded:")
    print(f"  Places:       {counts['places']}")
    print(f"  Aliases:      {counts['aliases']}")
    print(f"  Sources:      {counts['sources']}")
    print(f"  Observations: {counts['observations']}")


if __name__ == "__main__":
    main()
