# AGENT.md — CivicPulse Backend (concise agent guide)

## Critical Instructions

1. **Python Management**:
   - Always use `uv` for running and managing python.
      - Examples:
        - `uv run python ...` to execute a Python script.
        - `uv add ...` to install Python packages.
        - `uv sync` to synchronize Python dependencies.
      - See `uv --help` for more details.

2. **Celery Tasks**:
   - Background tasks (geocoding, imports) run via Celery.
   - Start worker: `uv run celery -A example worker -l info`

3. **GIS System Requirements**:
   - GeoDjango requires GDAL, GEOS, PROJ system libraries.
   - Dev uses SpatiaLite; prod uses PostGIS.

## Documentation References

**GeoDjango (spatial database)**:
- https://docs.djangoproject.com/en/stable/ref/contrib/gis/
- https://docs.djangoproject.com/en/stable/ref/contrib/gis/tutorial/
- https://docs.djangoproject.com/en/stable/ref/contrib/gis/db-api/

**Celery (background tasks)**:
- https://docs.celeryq.dev/en/stable/

**Leaflet.js (interactive maps)**:
- https://leafletjs.com/reference.html

**OSRM (route optimization)**:
- https://project-osrm.org/docs/v5.24.0/api/

**Geocoding APIs**:
- OpenCage: https://opencagedata.com/api
- Nominatim: https://nominatim.org/release-docs/develop/api/Search/