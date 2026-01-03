"""
Management command to import Census Bureau TIGER/Line shapefiles into District model.

This command reads ESRI shapefiles containing geographic boundaries (counties, congressional
districts, state legislative districts, etc.) and imports them into the District model with
proper CRS transformation and geometry handling.

Example usage:
    # Import Georgia counties
    python manage.py import_tiger_shapefile \
        data/tl_2024_13_county/tl_2024_13_county.shp \
        --district-type county \
        --state GA \
        --effective-date 2024-01-01

    # Dry run to preview
    python manage.py import_tiger_shapefile \
        data/tl_2024_13_sldl/tl_2024_13_sldl.shp \
        --district-type state_house \
        --state GA \
        --dry-run
"""

import logging
from datetime import date
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from civicpulse.models import District

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import Census TIGER/Line shapefile into District model"

    def add_arguments(self, parser):
        # Positional argument
        parser.add_argument(
            "shapefile_path",
            type=str,
            help="Path to the shapefile (.shp)",
        )

        # Required arguments
        parser.add_argument(
            "--district-type",
            type=str,
            required=True,
            choices=[choice[0] for choice in District.DistrictType.choices],
            help="Type of district",
        )

        # Optional arguments
        parser.add_argument(
            "--state",
            type=str,
            help="Two-letter state code (e.g., GA, CA). If not provided, extracted from GEOID if possible.",
        )
        parser.add_argument(
            "--identifier-field",
            type=str,
            default="GEOID",
            help="Shapefile attribute field for district identifier (default: GEOID)",
        )
        parser.add_argument(
            "--name-field",
            type=str,
            default="NAME",
            help="Shapefile attribute field for district name (default: NAME)",
        )
        parser.add_argument(
            "--county-field",
            type=str,
            help="Shapefile attribute field for county name (optional)",
        )
        parser.add_argument(
            "--effective-date",
            type=str,
            help="Date boundaries took effect (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--source",
            type=str,
            default="Census TIGER/Line",
            help="Data source description (default: 'Census TIGER/Line')",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and preview import without saving to database",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing districts if they already exist (default: skip duplicates)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed progress for each feature",
        )

    def handle(self, *args, **options):
        # Extract options
        shapefile_path = Path(options["shapefile_path"])
        district_type = options["district_type"]
        state = options.get("state")
        identifier_field = options["identifier_field"]
        name_field = options["name_field"]
        county_field = options.get("county_field")
        effective_date = options.get("effective_date")
        source = options["source"]
        dry_run = options["dry_run"]
        update_existing = options["update_existing"]
        verbose = options["verbose"]

        # Validate shapefile exists
        if not shapefile_path.exists():
            raise CommandError(f"Shapefile not found: {shapefile_path}")

        # Check for required companion files
        required_extensions = [".shp", ".shx", ".dbf", ".prj"]
        for ext in required_extensions:
            companion_file = shapefile_path.with_suffix(ext)
            if not companion_file.exists():
                raise CommandError(
                    f"Missing required file: {companion_file}. "
                    f"ESRI shapefiles require .shp, .shx, .dbf, and .prj files."
                )

        # Parse effective_date if provided
        parsed_effective_date = None
        if effective_date:
            try:
                parsed_effective_date = date.fromisoformat(effective_date)
            except ValueError as e:
                raise CommandError(
                    f"Invalid effective_date format: {effective_date}. "
                    f"Expected YYYY-MM-DD. Error: {e}"
                )

        self.stdout.write(self.style.SUCCESS(f"\nImporting shapefile: {shapefile_path}"))
        self.stdout.write(f"District type: {district_type}")
        self.stdout.write(f"Source: {source}")
        if state:
            self.stdout.write(f"State: {state}")
        if parsed_effective_date:
            self.stdout.write(f"Effective date: {parsed_effective_date}")
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be saved")
            )
        self.stdout.write("")

        # Read and transform shapefile
        gdf = self._read_and_transform_shapefile(shapefile_path)

        # Validate required fields exist
        self._validate_fields(gdf, identifier_field, name_field, county_field)

        # Process features
        created, updated, skipped, errors = self._process_features(
            gdf=gdf,
            district_type=district_type,
            state=state,
            identifier_field=identifier_field,
            name_field=name_field,
            county_field=county_field,
            effective_date=parsed_effective_date,
            source=source,
            dry_run=dry_run,
            update_existing=update_existing,
            verbose=verbose,
        )

        # Display summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("IMPORT SUMMARY"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total features processed: {len(gdf)}")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Would create: {created} districts")
            )
            if update_existing:
                self.stdout.write(
                    self.style.WARNING(f"Would update: {updated} districts")
                )
            self.stdout.write(
                self.style.WARNING(f"Would skip: {skipped} districts")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Created: {created} districts"))
            if update_existing:
                self.stdout.write(self.style.SUCCESS(f"Updated: {updated} districts"))
            self.stdout.write(f"Skipped: {skipped} districts")

        if errors:
            self.stdout.write(
                self.style.ERROR(f"\nErrors encountered: {len(errors)}")
            )
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  {error}"))
            raise CommandError(
                f"Import completed with {len(errors)} errors. "
                f"See above for details."
            )
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Import completed successfully!"))

    def _read_and_transform_shapefile(self, shapefile_path):
        """
        Read shapefile using GeoPandas and transform to EPSG:4326 (WGS84).

        Args:
            shapefile_path: Path to .shp file

        Returns:
            GeoDataFrame with geometries in EPSG:4326

        Raises:
            CommandError: If shapefile cannot be read or CRS transformation fails
        """
        try:
            import geopandas as gpd
        except ImportError as e:
            raise CommandError(
                "GeoPandas is required for shapefile import. "
                "Install with: uv sync --extra geo"
            ) from e

        try:
            # Read shapefile
            self.stdout.write(f"Reading shapefile...")
            gdf = gpd.read_file(shapefile_path)

            self.stdout.write(f"✓ Read {len(gdf)} features from shapefile")
            self.stdout.write(f"  Original CRS: {gdf.crs}")

            # Transform to WGS84 (EPSG:4326) if needed
            if gdf.crs is None:
                self.stdout.write(
                    self.style.WARNING(
                        "  WARNING: Shapefile has no CRS defined. "
                        "Assuming EPSG:4326 (WGS84)."
                    )
                )
                gdf.set_crs("EPSG:4326", inplace=True)
            elif gdf.crs != "EPSG:4326":
                self.stdout.write(f"  Transforming to EPSG:4326...")
                gdf = gdf.to_crs("EPSG:4326")
                self.stdout.write(f"  ✓ CRS transformation complete")

            return gdf

        except Exception as e:
            raise CommandError(f"Error reading shapefile: {e}") from e

    def _validate_fields(self, gdf, identifier_field, name_field, county_field):
        """
        Validate that required attribute fields exist in the shapefile.

        Args:
            gdf: GeoDataFrame from shapefile
            identifier_field: Field name for district identifier
            name_field: Field name for district name
            county_field: Field name for county (optional)

        Raises:
            CommandError: If required fields are missing
        """
        available_fields = list(gdf.columns)
        self.stdout.write(f"Available fields: {', '.join(available_fields)}")

        if identifier_field not in available_fields:
            raise CommandError(
                f"Identifier field '{identifier_field}' not found in shapefile. "
                f"Available fields: {', '.join(available_fields)}. "
                f"Use --identifier-field to specify a different field."
            )

        if name_field not in available_fields:
            raise CommandError(
                f"Name field '{name_field}' not found in shapefile. "
                f"Available fields: {', '.join(available_fields)}. "
                f"Use --name-field to specify a different field."
            )

        if county_field and county_field not in available_fields:
            self.stdout.write(
                self.style.WARNING(
                    f"County field '{county_field}' not found in shapefile. "
                    f"County field will be left blank."
                )
            )

    def _process_features(
        self,
        gdf,
        district_type,
        state,
        identifier_field,
        name_field,
        county_field,
        effective_date,
        source,
        dry_run,
        update_existing,
        verbose,
    ):
        """
        Process each feature in the GeoDataFrame and create/update District objects.

        Args:
            gdf: GeoDataFrame with district features
            district_type: District type (county, congressional, etc.)
            state: State code (if provided)
            identifier_field: Field name for identifier
            name_field: Field name for name
            county_field: Field name for county (optional)
            effective_date: Date boundaries took effect
            source: Data source description
            dry_run: If True, don't save to database
            update_existing: If True, update existing districts
            verbose: If True, show progress for each feature

        Returns:
            Tuple of (created_count, updated_count, skipped_count, errors_list)
        """
        total = len(gdf)
        created = 0
        updated = 0
        skipped = 0
        errors = []

        self.stdout.write(f"\nProcessing {total} features...")

        for idx, row in gdf.iterrows():
            try:
                # Extract attributes
                identifier = str(row[identifier_field]).strip()
                name = str(row[name_field]).strip()

                # Extract county if field specified
                county = None
                if county_field and county_field in row:
                    county = str(row[county_field]).strip()

                # Determine state code
                feature_state = state or self._extract_state_from_geoid(identifier)

                # Get geometry and convert to MultiPolygon
                geom_wkt = row.geometry.wkt
                geom = self._ensure_multipolygon(geom_wkt)

                if verbose:
                    self.stdout.write(
                        f"  Feature {idx + 1}/{total}: {name} ({identifier}) - State: {feature_state}"
                    )

                if dry_run:
                    # Dry run: just validate and report
                    self.stdout.write(
                        f"  Would import: {name} ({identifier}) "
                        f"[{district_type}, {feature_state}]"
                    )
                    created += 1
                else:
                    # Create or update district
                    with transaction.atomic():
                        defaults = {
                            "name": name,
                            "boundary": geom,
                            "source": source,
                        }
                        if effective_date:
                            defaults["effective_date"] = effective_date
                        if county:
                            defaults["county"] = county

                        district, was_created = District.objects.update_or_create(
                            district_type=district_type,
                            state=feature_state,
                            identifier=identifier,
                            defaults=defaults,
                        )

                        if was_created:
                            created += 1
                            if verbose:
                                self.stdout.write(
                                    self.style.SUCCESS(f"    ✓ Created: {name}")
                                )
                        else:
                            if update_existing:
                                updated += 1
                                if verbose:
                                    self.stdout.write(
                                        self.style.SUCCESS(f"    ✓ Updated: {name}")
                                    )
                            else:
                                skipped += 1
                                if verbose:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f"    - Skipped (already exists): {name}"
                                        )
                                    )

                # Progress reporting every 50 features
                if (idx + 1) % 50 == 0 and not verbose:
                    self.stdout.write(f"  Processed {idx + 1}/{total} features...")

            except Exception as e:
                error_msg = f"Feature {idx + 1} ({name if 'name' in locals() else 'unknown'}): {e}"
                errors.append(error_msg)
                logger.error(error_msg)

                # Stop after 10 errors
                if len(errors) >= 10:
                    self.stdout.write(
                        self.style.ERROR(
                            f"\n  ✗ Too many errors ({len(errors)}), stopping import..."
                        )
                    )
                    break

        return created, updated, skipped, errors

    def _ensure_multipolygon(self, geom_wkt):
        """
        Convert WKT geometry to MultiPolygon for Django GIS.

        The District model uses MultiPolygonField, but some shapefiles contain
        Polygon geometries. This function converts Polygon to MultiPolygon and
        validates geometry types.

        Args:
            geom_wkt: WKT (Well-Known Text) string representation of geometry

        Returns:
            MultiPolygon geometry with SRID 4326

        Raises:
            ValueError: If geometry type is not Polygon or MultiPolygon
        """
        geom = GEOSGeometry(geom_wkt, srid=4326)

        if geom.geom_type == "Polygon":
            return MultiPolygon([geom], srid=4326)
        elif geom.geom_type == "MultiPolygon":
            return geom
        else:
            raise ValueError(
                f"Unsupported geometry type: {geom.geom_type}. "
                f"Expected Polygon or MultiPolygon."
            )

    def _extract_state_from_geoid(self, geoid):
        """
        Extract state FIPS code from GEOID field.

        TIGER/Line GEOIDs typically start with a 2-digit state FIPS code.
        For example:
        - County GEOID: "13121" → state = "13" (Georgia)
        - Congressional: "1301" → state = "13"
        - State House: "13001" → state = "13"

        Args:
            geoid: GEOID string from shapefile

        Returns:
            First 2 characters of GEOID, or None if invalid

        Note:
            This returns the numeric FIPS code, not the 2-letter state abbreviation.
            To convert FIPS to abbreviation, use a mapping dict or require --state flag.
        """
        if geoid and len(geoid) >= 2:
            return geoid[:2]
        return None
