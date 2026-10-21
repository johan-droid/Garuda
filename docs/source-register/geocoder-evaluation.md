# Geocoder & Search Evaluation

## Evaluated Geocoder: OpenStreetMap Nominatim
- **Endpoint:** `https://nominatim.openstreetmap.org/search`
- **Policy:** Requires custom HTTP User-Agent; max 1 req/sec; no bulk scraping
- **Local Fallback:** Garuda SQLite `places` search (instant, zero network requirement)

## Test Query Log (Khordha District, Odisha)

| Query | Expected Result | Result Status | Lat/Lng | Match Type |
|-------|-----------------|---------------|---------|------------|
| `odisha` | State of Odisha | 200 OK | 20.9517, 85.0985 | Canonical name |
| `orissa` | State of Odisha | 200 OK | 20.9517, 85.0985 | Historic alias |
| `bhubaneswar` | District HQ / Capital | 200 OK | 20.2961, 85.8245 | Canonical name |
| `khordha` | District | 200 OK | 20.1834, 85.6171 | Canonical name |
