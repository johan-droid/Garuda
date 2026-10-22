# 🦅 Garuda — Master Production & Operations Documentation

> **Document Version:** 1.0  
> **Target Release:** Version 1.0 (Credible Place Intelligence)  
> **Audience:** DevOps Engineers, System Administrators, Security Auditors & Developers  

---

## 📑 Table of Contents

1. [Architecture & System Design](#1-architecture--system-design)
2. [Production Deployment Options](#2-production-deployment-options)
3. [Configuration & Environment Variables](#3-configuration--environment-variables)
4. [Database Operations & Persistence](#4-database-operations--persistence)
5. [Anti-Hallucination & Safety Governance](#5-anti-hallucination--safety-governance)
6. [Security Hardening & Compliance Checklist](#6-security-hardening--compliance-checklist)
7. [Health Probes, Observability & Diagnostics](#7-health-probes-observability--diagnostics)
8. [Operations & Incident Response Runbook](#8-operations--incident-response-runbook)
9. [Continuous Integration & Quality Gates](#9-continuous-integration--quality-gates)
10. [Pilot District Scope & Expansion Strategy](#10-pilot-district-scope--expansion-strategy)

---

## 🏛️ 1. Architecture & System Design

Garuda operates on a **zero-planned-spend, local-first architecture**. It combines a high-performance Python/FastAPI backend with a lightweight, installable TypeScript/React PWA.

```mermaid
flowchart TD
    Client["Client Devices<br/>(Android PWA, Desktop Browser)"]
    Proxy["Nginx / Caddy Reverse Proxy<br/>(SSL, Rate Limiting, Static Assets)"]
    FastAPI["FastAPI Application Server<br/>(Port 8000, Python 3.12+)"]
    Cache["In-Memory Cache & TTL Engine<br/>(Staleness Tracking)"]
    DB[("SQLite WAL Database<br/>(garuda_local.db)")]
    GeoJSON["Boundary Fixture Engine<br/>(Ray-Casting Reverse Geocoder)"]

    Client -->|HTTPS / WSS| Proxy
    Proxy -->|Static PWA Shell| Client
    Proxy -->|API Requests <code>/api/v1/*</code>| FastAPI
    FastAPI -->|Cached Observations| Cache
    FastAPI -->|Spatial Point Lookup| GeoJSON
    FastAPI -->|Relational Queries| DB
```

### Component Responsibility Matrix

| Component | Technology | Primary Role | Safety & Resilience Rules |
|-----------|------------|--------------|---------------------------|
| **Frontend** | React 18, Vite, TypeScript | Single responsive UI & MapLibre map | Graceful offline degradation, zero fake zero display |
| **Backend** | Python 3.12+, FastAPI, Pydantic v2 | Typed API contracts, validation, spatial reverse geocoding | Input bounds, rate-limiting, safe logging |
| **Storage** | SQLite 3.35+ (WAL Mode) | Relational store for places, sources, observations | Foreign keys enforced, atomic batch imports |
| **Spatial Engine** | Native Ray Casting / Haversine | Point-in-polygon resolution for admin hierarchy | Fallback to nearest centroid if outside boundaries |

---

## 🚀 2. Production Deployment Options

### Option A: Native Linux Service (Systemd) — Recommended for Local/VPS

#### 1. System Dependencies
```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv nodejs npm nginx
```

#### 2. Backend Service Setup (`/etc/systemd/system/garuda-backend.service`)
```ini
[Unit]
Description=Garuda India Place Intelligence API
After=network.target

[Service]
Type=simple
User=garuda
WorkingDirectory=/opt/garuda/backend
Environment="PATH=/opt/garuda/.venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/opt/garuda/.env
ExecStart=/opt/garuda/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start backend:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now garuda-backend
```

#### 3. Frontend Static Build & Hosting
```bash
cd /opt/garuda/frontend
npm install
npm run build
# Built files placed in /opt/garuda/frontend/dist
```

#### 4. Nginx Reverse Proxy Configuration (`/etc/nginx/sites-available/garuda`)
```nginx
server {
    listen 80;
    server_name garuda.internal;

    # Serve built React PWA
    location / {
        root /opt/garuda/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
        expires 1h;
        add_header Cache-Control "public, no-transform";
    }

    # Proxy API requests
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health probe bypass
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/garuda /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## ⚙️ 3. Configuration & Environment Variables

All settings are managed via environment variables and validated by `app.core.config.Settings` (Pydantic Settings).

| Variable | Type | Default Value | Production Recommendation | Description |
|----------|------|---------------|---------------------------|-------------|
| `ENVIRONMENT` | string | `development` | `production` | Enables strict production error handling and security controls |
| `DATABASE_URL` | string | `sqlite:///garuda_local.db` | `sqlite:////var/data/garuda.db` or PostgreSQL | Database connection string |
| `ADMIN_API_KEY` | string | `garuda-local-dev-admin-key-2026` | Generate 32+ char random key | Bearer key for `/api/v1/admin/*` dataset ingestion |
| `SECRET_KEY` | string | `garuda-insecure-dev-secret...` | Generate 32+ char random key | Key for request signing and cryptographic tokens |
| `RATE_LIMIT_ENABLED` | bool | `true` | `true` | Enables sliding window rate limiting on public endpoints |
| `RATE_LIMIT_PER_MINUTE` | int | `60` | `60` to `120` | Max requests per IP per minute |
| `LOG_JSON` | bool | `false` | `true` | Emits structured JSON logs for ingest by Promtail/Datadog |
| `LOG_LEVEL` | string | `INFO` | `INFO` | Logging threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CORS_ORIGINS` | JSON list | `["http://localhost:5173"]` | `["https://garuda.yourdomain.in"]` | Allowed browser origins |
| `MAX_PAYLOAD_SIZE` | int | `2097152` (2MB) | `2097152` | Max allowable HTTP body size |
| `DB_TIMEOUT` | int | `30` | `30` | SQLite lock wait timeout in seconds |

---

## 🗄️ 4. Database Operations & Persistence

### SQLite WAL Mode Configuration
Garuda configures SQLite with **WAL (Write-Ahead Logging)** mode and explicit foreign key constraints in `app.db.session`:
```python
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```
This enables concurrent reads without blocking writes and prevents database locking.

### Hot Backup Runbook (Zero Downtime)
SQLite WAL mode allows hot backups while the service is actively serving traffic:

```bash
#!/bin/bash
# /opt/scripts/backup_garuda.sh
BACKUP_DIR="/var/backups/garuda"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

# Perform atomic hot backup
sqlite3 garuda_local.db ".backup '$BACKUP_DIR/garuda_$TIMESTAMP.db'"

# Compress and keep 14 days of backups
gzip "$BACKUP_DIR/garuda_$TIMESTAMP.db"
ln -sf "$BACKUP_DIR/garuda_$TIMESTAMP.db.gz" "$BACKUP_DIR/garuda_latest.db.gz"
find "$BACKUP_DIR" -type f -name "*.db.gz" -mtime +14 -delete
```

### PostgreSQL + PostGIS Upgrade Path
When dataset volume exceeds local capacity, switch backend to PostgreSQL:
```env
DATABASE_URL=postgresql+psycopg://garuda_user:secure_pass@localhost:5432/garuda_prod
```
The SQLAlchemy schema (`app.models.entities`) is 100% agnostic and executes on PostgreSQL without code changes.

---

## 🛡️ 5. Anti-Hallucination & Safety Governance

### Health Data Classification Framework

Every health data point is classified into exactly one category:

```mermaid
stateDiagram-v2
    [*] --> Classification
    Classification --> OfficialAlert: Competent Public Health Authority (Dated statement)
    Classification --> HistoricalCases: Closed surveillance period (e.g. 2024 counts)
    Classification --> RoutineSurveillance: Ongoing monitoring (e.g. IDSP weekly)
    Classification --> GeneralPrevention: Authoritative guidance (WHO, MoHFW)
    Classification --> Unavailable: No permitted verified source

    OfficialAlert --> DisplayAlert: Active window (valid_from <= now <= valid_until)
    OfficialAlert --> DisplayExpired: Lapsed window (strictly marked Expired)
```

### Safety Rules Implemented in Code
1. **Mandatory Prevention Guidance**: Any official alert requires an `issuing_authority`, valid dates, and a link to authoritative prevention guidance (WHO/MoHFW).
2. **No Medical Advice**: Every health panel renders the disclaimer: *"🛡️ Safety Principle: Garuda does not provide individual health diagnosis. Informational institutional surveillance only."*
3. **No Fake Zeros**: Missing fields return `status: "unavailable"` and populate `data_gaps`.
4. **Historical Labeling**: 2011 Census metrics are stamped `Historical (2011)`.

---

## 🔒 6. Security Hardening & Compliance Checklist

| Category | Control | Verification Command / Metric | Status |
|----------|---------|--------------------------------|--------|
| **Secrets** | Zero committed credentials | `git log -p \| grep -i "password\|api_key"` | PASSED |
| **Headers** | Security Headers Middleware | `X-Content-Type-Options: nosniff`<br/>`X-Frame-Options: DENY`<br/>`Content-Security-Policy` | ENFORCED |
| **Rate Limit** | IP Sliding Window | Max 60 req/min on public routes; 429 response | ENFORCED |
| **Admin Route** | Bearer Key Auth | `/api/v1/admin/*` rejects invalid/missing keys | ENFORCED |
| **Input Bounds** | Query string truncation | Search query capped at 500 chars; pagination max 50 | ENFORCED |
| **SQL Injection** | Parameterized ORM | SQLAlchemy 2.0 Core/ORM queries only | ENFORCED |

---

## 📡 7. Health Probes, Observability & Diagnostics

### Health Endpoints
- **Operational Health**: `GET /health` → returns version, environment, and pilot region.
- **Liveness Probe**: `GET /health/live` → returns 200 OK if FastAPI process is alive.
- **Readiness Probe**: `GET /health/ready` → executes `SELECT 1` on database; returns 503 if database connection fails.

### Source Diagnostics
`GET /api/v1/sources/diagnostics` returns real-time status of all connected source adapters:
```json
{
  "total_sources": 7,
  "sources": [
    {
      "source_id": "src-census-2011",
      "publisher": "Office of the Registrar General, India",
      "name": "Census of India 2011 Primary Census Abstract",
      "status": "healthy",
      "records_served": 50,
      "ttl_seconds": 86400,
      "error_status": null
    }
  ]
}
```

---

## 🚨 8. Operations & Incident Response Runbook

### Scenario 1: Database Locked (`sqlite3.OperationalError: database is locked`)
1. **Cause**: A write transaction exceeded `DB_TIMEOUT` (30 seconds).
2. **Mitigation**:
   ```bash
   # Check active connections
   lsof garuda_local.db
   # Verify WAL checkpointing
   sqlite3 garuda_local.db "PRAGMA wal_checkpoint(FULL);"
   ```
3. Ensure no long-running external processes are holding SQLite write locks.

### Scenario 2: Data Source Unavailable or Stale
1. Garuda gracefully flags the panel as `status: "stale"` or `status: "unavailable"`.
2. The user interface displays a yellow "Stale" or grey "Unavailable" badge.
3. System continues serving cached records with complete transparency.

### Scenario 3: Emergency Data Rollback
To restore a known good database snapshot safely without risking partial writes or database corruption:

```bash
# 1. Stop backend service to halt all active database sessions and writes
sudo systemctl stop garuda-backend

# 2. Verify backup archive exists and gzip integrity is uncompromised
BACKUP_ARCHIVE="/var/backups/garuda/garuda_latest.db.gz"
if [ ! -f "$BACKUP_ARCHIVE" ]; then
    echo "ERROR: Backup archive $BACKUP_ARCHIVE not found!" >&2
    exit 1
fi
gzip -t "$BACKUP_ARCHIVE" || { echo "ERROR: Backup archive corrupted!" >&2; exit 1; }

# 3. Decompress into a temporary file on the target filesystem
TMP_RESTORE="/opt/garuda/garuda_local.db.restore_tmp"
gunzip -c "$BACKUP_ARCHIVE" > "$TMP_RESTORE"

# 4. Verify SQLite database integrity before swapping
INTEGRITY=$(python3 -c "import sqlite3; con=sqlite3.connect('$TMP_RESTORE'); res=con.execute('PRAGMA integrity_check').fetchone()[0]; print(res)")
if [ "$INTEGRITY" != "ok" ]; then
    echo "ERROR: Restored database failed integrity check: $INTEGRITY" >&2
    rm -f "$TMP_RESTORE"
    exit 1
fi

# 5. Set correct service ownership and permissions
sudo chown garuda:garuda "$TMP_RESTORE"
chmod 640 "$TMP_RESTORE"

# 6. Atomically replace database file
sudo mv "$TMP_RESTORE" /opt/garuda/garuda_local.db
sudo rm -f /opt/garuda/garuda_local.db-wal /opt/garuda/garuda_local.db-shm

# 7. Restart service and verify health readiness
sudo systemctl start garuda-backend
curl -f http://127.0.0.1:8000/health/ready || {
    echo "CRITICAL: Service failed readiness check following restore!" >&2
    exit 1
}
```

#### Recovery if Restoration or Startup Fails
If `PRAGMA integrity_check` fails on the latest archive:
1. Inspect available timestamped archives: `ls -lt /var/backups/garuda/garuda_*.db.gz`
2. Select the next most recent timestamped archive and repeat steps 2–7 with that specific file.
3. If all archives are corrupt, reinitialize and reseed the base pilot dataset:
   ```bash
   cd /opt/garuda/backend
   python3 -m app.db.init_db
   python3 seed_pilot.py
   sudo systemctl restart garuda-backend
   ```

---

## 🔄 9. Continuous Integration & Quality Gates

The CI pipeline runs automated checks on every push:

```bash
# 1. Backend Linting & Type Checking
make lint

# 2. Automated Test Suite (52 tests)
make test

# 3. Frontend Production Build Check
make build
```

Every PR must pass all 52 unit, contract, and edge-case tests before deployment.

---

## 🗺️ 10. Pilot District Scope & Expansion Strategy

The pilot deployment is validated for **Khordha District, Odisha** (`IN-OD-29`).

### Staged Regional Expansion Strategy
When expanding to adjoining districts (Puri, Cuttack, Ganjam):
1. **Source Registration**: Register local district publications in `/api/v1/sources`.
2. **Boundary Validation**: Add district and block polygons to `khordha_pilot.geojson` (or separate regional GeoJSON file).
3. **Data Ingestion**: Execute atomic batch import using `backend/seed_pilot.py` or `POST /api/v1/admin/import`.
4. **Verification Audit**: Validate all 10 non-negotiable principles before removing demo tags.
