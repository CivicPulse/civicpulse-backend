"""
Django management command for importing district GIS data.

This command imports district data from shapefiles and KML/KMZ files.

This command provides functionality to:
- Import electoral district data from shapefiles (.shp, .shx, .dbf)
- Import electoral district data from KML/KMZ files
- Extract district boundaries and metadata
- Auto-generate district codes
- Handle duplicate detection
- Optionally auto-assign people to imported districts

Usage Examples:
    # Import congressional districts for Pennsylvania
    python manage.py import_districts pa_congress.shp \\
        --district-type federal_house --state PA

    # Dry run with KML file
    python manage.py import_districts districts.kml \\
        --district-type state_senate --state PA --dry-run

    # Import and auto-assign people
    python manage.py import_districts school_districts.shp \\
        --district-type school_board --state PA --assign-people
"""

import re
import zipfile
from pathlib import Path
from typing import Any

import fiona
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from fastkml import kml
from loguru import logger

from civicpulse.models import District
from civicpulse.services.district_assignment import DistrictAssignmentService


class Command(BaseCommand):
    """
    Management command for importing district GIS data.

    This command supports importing electoral district boundaries and metadata from:
    - ESRI Shapefiles (.shp with .shx and .dbf components)
    - KML (Keyhole Markup Language) files
    - KMZ (Compressed KML) files

    The command provides:
    - Comprehensive error handling and validation
    - Progress reporting with colored output
    - Dry-run mode for previewing imports
    - Automatic district code generation
    - Duplicate detection and handling
    - Post-import person-to-district assignment

    Attributes:
        help: Command help text displayed in Django's management command listing
    """

    help = "Import district GIS data from shapefiles and KML/KMZ files"

    def add_arguments(self, parser) -> None:
        """
        Define command-line arguments for the import_districts command.

        Args:
            parser: Django ArgumentParser instance to add arguments to
        """
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to shapefile or KML/KMZ file",
        )
        parser.add_argument(
            "--district-type",
            choices=[
                "federal_senate",
                "federal_house",
                "state_senate",
                "state_house",
                "county",
                "school_board",
                "municipality",
                "other",
            ],
            required=True,
            help="Type of districts to import",
        )
        parser.add_argument(
            "--state",
            type=str,
            help="Two-letter state code (e.g., PA)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview import without saving to database",
        )
        parser.add_argument(
            "--assign-people",
            action="store_true",
            help="Auto-assign people to imported districts after import",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Main entry point for the import_districts command.

        This method orchestrates the entire import process:
        1. Validates input file and arguments
        2. Determines file type (shapefile, KML, or KMZ)
        3. Parses the file to extract district data
        4. Creates District instances (or previews in dry-run mode)
        5. Optionally assigns people to districts
        6. Reports comprehensive statistics

        Args:
            *args: Positional arguments (unused)
            **options: Dictionary of command-line options including:
                - file_path: Path to input file
                - district_type: Type of districts to import
                - state: Two-letter state code
                - dry_run: Boolean flag for preview mode
                - assign_people: Boolean flag for post-import assignment

        Raises:
            CommandError: If file validation fails or critical errors occur
        """
        file_path = Path(options["file_path"])
        district_type = options["district_type"]
        state = options.get("state", "").upper()
        dry_run = options["dry_run"]
        assign_people = options["assign_people"]

        # Validate file exists
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        # Validate state if provided
        if state and not re.match(r"^[A-Z]{2}$", state):
            raise CommandError(
                f"Invalid state code: {state}. Must be 2 uppercase letters (e.g., PA)"
            )

        # Log import start
        logger.info(f"Starting district import from {file_path}")
        logger.info(f"District type: {district_type}")
        logger.info(f"State: {state or 'Not specified'}")
        logger.info(f"Dry run: {dry_run}")

        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 70}"))
        self.stdout.write(
            self.style.SUCCESS(f"Importing districts from: {file_path.name}")
        )
        self.stdout.write(self.style.SUCCESS(f"{'=' * 70}\n"))

        try:
            # Determine file type and parse
            file_extension = file_path.suffix.lower()

            if file_extension == ".shp":
                district_data_list = self.parse_shapefile(str(file_path))
            elif file_extension in [".kml", ".kmz"]:
                district_data_list = self.parse_kml(str(file_path))
            else:
                raise CommandError(
                    f"Unsupported file type: {file_extension}. "
                    "Supported types: .shp, .kml, .kmz"
                )

            if not district_data_list:
                self.stdout.write(
                    self.style.WARNING("No district features found in file")
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"Found {len(district_data_list)} district features\n"
                )
            )

            # Process districts
            stats = self._process_districts(
                district_data_list, district_type, state, dry_run
            )

            # Display statistics
            self._display_statistics(stats, dry_run)

            # Auto-assign people if requested
            if assign_people and not dry_run and stats["created"] > 0:
                self._assign_people_to_districts()

            # Final message
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        "\nDRY RUN MODE - No changes were saved to the database"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nSuccessfully imported {stats['created']} districts"
                    )
                )

        except Exception as e:
            logger.error(f"Error during district import: {e}", exc_info=True)
            raise CommandError(f"Import failed: {e}") from e

    def parse_shapefile(self, file_path: str) -> list[dict[str, Any]]:
        """
        Parse an ESRI shapefile and extract district data.

        This method uses the fiona library to read shapefile features and
        extract both geometry (district boundaries) and properties (metadata).

        The method:
        1. Opens the shapefile using fiona
        2. Iterates through all features
        3. Extracts geometry (converted to WKT format)
        4. Extracts properties (district name, code, metadata)
        5. Standardizes field names for downstream processing

        Args:
            file_path: Absolute path to the .shp file

        Returns:
            List of dictionaries, each containing:
                - geometry: Geometry object or WKT string
                - properties: Dictionary of feature attributes (name, code, etc.)

        Raises:
            fiona.errors.DriverError: If shapefile cannot be opened or is corrupted
            Exception: For other unexpected errors during parsing

        Example:
            >>> cmd = Command()
            >>> data = cmd.parse_shapefile('/path/to/districts.shp')
            >>> print(f"Parsed {len(data)} features")
            >>> print(data[0]['properties']['name'])
        """
        logger.info(f"Parsing shapefile: {file_path}")
        district_data_list = []

        try:
            with fiona.open(file_path, "r") as shapefile:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Opened shapefile with {len(shapefile)} features"
                    )
                )
                logger.info(f"Shapefile CRS: {shapefile.crs}")
                logger.info(f"Shapefile schema: {shapefile.schema}")

                for feature in shapefile:
                    try:
                        district_data = {
                            "geometry": feature["geometry"],
                            "properties": feature.get("properties", {}),
                        }
                        district_data_list.append(district_data)
                    except Exception as e:
                        logger.error(f"Error parsing feature: {e}", exc_info=True)
                        self.stdout.write(
                            self.style.WARNING(f"Skipping invalid feature: {e}")
                        )
                        continue

            logger.info(
                f"Successfully parsed {len(district_data_list)} features from shapefile"
            )
            return district_data_list

        except Exception as e:
            logger.error(f"Error reading shapefile {file_path}: {e}", exc_info=True)
            raise CommandError(f"Failed to read shapefile: {e}") from e

    def parse_kml(self, file_path: str) -> list[dict[str, Any]]:
        """
        Parse a KML or KMZ file and extract district data.

        This method uses the fastkml library to parse KML documents and
        extract Placemark features representing district boundaries.

        The method:
        1. Handles KMZ (compressed) files by extracting doc.kml
        2. Parses KML document structure
        3. Iterates through Placemark features
        4. Extracts geometry (converted to WKT format)
        5. Extracts name and ExtendedData for metadata
        6. Standardizes field names for downstream processing

        Args:
            file_path: Absolute path to the .kml or .kmz file

        Returns:
            List of dictionaries, each containing:
                - geometry: Geometry object or WKT string
                - properties: Dictionary of feature attributes (name, metadata)

        Raises:
            zipfile.BadZipFile: If KMZ file is corrupted
            xml.etree.ElementTree.ParseError: If KML XML is malformed
            Exception: For other unexpected errors during parsing

        Example:
            >>> cmd = Command()
            >>> data = cmd.parse_kml('/path/to/districts.kmz')
            >>> print(f"Parsed {len(data)} placemarks")
            >>> print(data[0]['properties']['name'])
        """
        logger.info(f"Parsing KML/KMZ file: {file_path}")
        district_data_list = []

        try:
            # Handle KMZ (compressed KML)
            if file_path.endswith(".kmz"):
                with zipfile.ZipFile(file_path, "r") as kmz:
                    # KMZ files typically contain doc.kml
                    kml_files = [
                        name for name in kmz.namelist() if name.endswith(".kml")
                    ]
                    if not kml_files:
                        raise CommandError("No KML file found in KMZ archive")
                    kml_content = kmz.read(kml_files[0])
            else:
                # Regular KML file
                with open(file_path, "rb") as kml_file:
                    kml_content = kml_file.read()

            # Parse KML
            k = kml.KML()
            k.from_string(kml_content.decode("utf-8"))

            # Extract features from KML
            feature_count = 0
            features_list = list(k.features())  # type: ignore[operator]
            for document in features_list:
                folders_list = list(document.features())
                for folder in folders_list:
                    placemarks_list = list(folder.features())
                    for placemark in placemarks_list:
                        try:
                            # Extract geometry
                            geometry = placemark.geometry

                            # Extract properties
                            properties = {
                                "name": placemark.name or "",
                                "description": placemark.description or "",
                            }

                            # Extract ExtendedData if available
                            if (
                                hasattr(placemark, "extended_data")
                                and placemark.extended_data
                            ):
                                for data in placemark.extended_data.elements:
                                    if hasattr(data, "name") and hasattr(data, "value"):
                                        properties[data.name] = data.value

                            district_data = {
                                "geometry": geometry,
                                "properties": properties,
                            }
                            district_data_list.append(district_data)
                            feature_count += 1

                        except Exception as e:
                            logger.error(
                                f"Error parsing KML placemark: {e}", exc_info=True
                            )
                            self.stdout.write(
                                self.style.WARNING(f"Skipping invalid placemark: {e}")
                            )
                            continue

            self.stdout.write(
                self.style.SUCCESS(f"Parsed {feature_count} placemarks from KML")
            )
            logger.info(
                f"Successfully parsed {len(district_data_list)} features from KML"
            )
            return district_data_list

        except Exception as e:
            logger.error(f"Error reading KML/KMZ file {file_path}: {e}", exc_info=True)
            raise CommandError(f"Failed to read KML/KMZ file: {e}") from e

    def extract_district_info(
        self, feature_data: dict[str, Any], district_type: str, state: str
    ) -> dict[str, Any]:
        """
        Extract and standardize district information from feature data.

        This method normalizes district data from various source formats
        (shapefiles, KML) into a consistent structure for District model creation.

        The method:
        1. Extracts district name from multiple possible field names
        2. Extracts or generates district code
        3. Extracts boundary geometry (simplified to WKT text for MVP)
        4. Extracts counties and ZIP codes from properties or geometry
        5. Extracts population and other metadata
        6. Validates and cleans extracted data

        Args:
            feature_data: Dictionary containing geometry and properties from parsed file
            district_type: Type of district (federal_house, state_senate, etc.)
            state: Two-letter state code

        Returns:
            Dictionary with standardized district fields:
                - name: District name
                - district_code: Unique district code (STATE-NN format)
                - district_type: Type of district
                - state: Two-letter state code
                - boundary_description: Text description of boundaries
                - counties_covered: List of county names
                - zip_codes_covered: List of ZIP codes
                - population: Integer population count
                - notes: Additional notes

        Example:
            >>> cmd = Command()
            >>> feature = {'geometry': {...}, 'properties': {'NAME': 'District 5'}}
            >>> info = cmd.extract_district_info(feature, 'federal_house', 'PA')
            >>> print(info['district_code'])  # 'PA-05'
        """
        properties = feature_data.get("properties", {})

        # Extract name - try common field names
        name_fields = ["NAME", "NAMELSAD", "name", "district_name", "DISTRICT"]
        name = ""
        for field in name_fields:
            if field in properties and properties[field]:
                name = str(properties[field]).strip()
                break

        if not name:
            name = f"District {len(properties)}"  # Fallback name

        # Extract district code - try common field names
        code_fields = ["GEOID", "CD116FP", "DISTRICT", "code", "district_code"]
        district_code = ""
        for field in code_fields:
            if field in properties and properties[field]:
                district_code = str(properties[field]).strip()
                break

        # Generate district code if not found (STATE-NN format)
        if not district_code:
            # Try to extract number from name
            match = re.search(r"\d+", name)
            if match:
                district_num = match.group()
                district_code = f"{state}-{district_num.zfill(2)}"
            else:
                # Use a default based on feature index
                district_code = f"{state}-{len(name)}"

        # Ensure district code is in correct format
        if not re.match(r"^[A-Z]{2}-\d+$", district_code):
            # Try to fix format
            if "-" not in district_code and state:
                district_code = f"{state}-{district_code}"

        # Extract geometry description
        geometry = feature_data.get("geometry", {})
        boundary_description = str(geometry.get("type", ""))

        # Extract counties - try common field names
        counties = []
        county_fields = ["COUNTY", "COUNTYFP", "counties", "county_name"]
        for field in county_fields:
            if field in properties and properties[field]:
                county_value = properties[field]
                if isinstance(county_value, list):
                    counties = county_value
                else:
                    counties = [str(county_value)]
                break

        # Extract ZIP codes - try common field names
        zip_codes = []
        zip_fields = ["ZCTA5CE10", "ZIP", "zip_code", "zipcode", "zip_codes"]
        for field in zip_fields:
            if field in properties and properties[field]:
                zip_value = properties[field]
                if isinstance(zip_value, list):
                    zip_codes = zip_value
                else:
                    zip_codes = [str(zip_value)]
                break

        # Extract population
        population = None
        pop_fields = ["POP", "POPULATION", "pop", "population", "POP10"]
        for field in pop_fields:
            if field in properties and properties[field]:
                try:
                    population = int(properties[field])
                    break
                except (ValueError, TypeError):
                    continue

        # Extract additional notes
        notes = properties.get("description", properties.get("NOTES", ""))

        return {
            "name": name,
            "district_code": district_code,
            "district_type": district_type,
            "state": state,
            "boundary_description": boundary_description,
            "counties_covered": counties,
            "zip_codes_covered": zip_codes,
            "population": population,
            "notes": notes,
        }

    @transaction.atomic
    def create_district(
        self, data: dict[str, Any], dry_run: bool = False
    ) -> District | None:
        """
        Create a District instance from extracted data.

        This method creates or updates District records in the database
        with proper validation and duplicate detection.

        The method:
        1. Validates district_code uniqueness
        2. Checks for existing districts with same code
        3. Creates District instance with all fields
        4. Performs model validation (clean())
        5. Saves to database (unless dry_run=True)
        6. Logs creation or skipping

        Args:
            data: Dictionary with district fields (from extract_district_info)
            dry_run: If True, validates but doesn't save to database

        Returns:
            District instance if created/updated, None if skipped or dry_run

        Raises:
            ValidationError: If district data fails validation
            IntegrityError: If database constraint violations occur

        Example:
            >>> cmd = Command()
            >>> data = {'name': 'District 5', 'district_code': 'PA-05', ...}
            >>> district = cmd.create_district(data, dry_run=False)
            >>> print(f"Created: {district.name}")
        """
        district_code = data.get("district_code")

        # Check for existing district
        if not dry_run:
            existing = District.objects.filter(district_code=district_code).first()
            if existing:
                logger.warning(
                    f"District with code {district_code} already exists, skipping"
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped: {data['name']} - code {district_code} already exists"
                    )
                )
                return None

        # Create district instance
        district = District(
            name=data["name"],
            district_code=data["district_code"],
            district_type=data["district_type"],
            state=data["state"],
            boundary_description=data.get("boundary_description", ""),
            counties_covered=data.get("counties_covered", []),
            zip_codes_covered=data.get("zip_codes_covered", []),
            population=data.get("population"),
            notes=data.get("notes", ""),
        )

        # Validate
        try:
            district.full_clean()
        except Exception as e:
            logger.error(
                f"Validation error for district {district_code}: {e}", exc_info=True
            )
            self.stdout.write(
                self.style.ERROR(f"Validation error for {data['name']}: {e}")
            )
            return None

        # Save (unless dry run)
        if not dry_run:
            try:
                district.save()
                logger.info(f"Created district: {district_code}")
                self.stdout.write(
                    self.style.SUCCESS(f"Created: {district.name} ({district_code})")
                )
            except Exception as e:
                logger.error(
                    f"Error saving district {district_code}: {e}", exc_info=True
                )
                self.stdout.write(self.style.ERROR(f"Error saving {data['name']}: {e}"))
                return None
        else:
            logger.debug(f"Dry run: Would create district {district_code}")

        return district

    def _process_districts(
        self,
        district_data_list: list[dict[str, Any]],
        district_type: str,
        state: str,
        dry_run: bool,
    ) -> dict[str, int]:
        """
        Process a list of district data and create District instances.

        This is a helper method that orchestrates the extraction and creation
        of districts from parsed file data.

        Args:
            district_data_list: List of feature dictionaries from parse methods
            district_type: Type of districts to create
            state: Two-letter state code
            dry_run: If True, preview without saving

        Returns:
            Dictionary with processing statistics:
                - total: Total features processed
                - created: Successfully created districts
                - skipped: Skipped districts (duplicates or errors)
                - errors: Districts that caused errors
        """
        stats = {
            "total": len(district_data_list),
            "created": 0,
            "skipped": 0,
            "errors": 0,
        }

        # Show sample of first 5 districts in dry-run mode
        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nSample of districts to import:"))
            self.stdout.write(self.style.SUCCESS("-" * 70))

        for i, feature_data in enumerate(district_data_list, start=1):
            try:
                # Extract standardized district info
                district_info = self.extract_district_info(
                    feature_data, district_type, state
                )

                # Show sample in dry-run mode
                if dry_run and i <= 5:
                    name = district_info["name"]
                    code = district_info["district_code"]
                    self.stdout.write(self.style.SUCCESS(f"\n{i}. {name} ({code})"))
                    self.stdout.write(f"   State: {district_info['state']}")
                    self.stdout.write(f"   Type: {district_info['district_type']}")
                    if district_info.get("population"):
                        pop = district_info["population"]
                        self.stdout.write(f"   Population: {pop:,}")
                    if district_info.get("counties_covered"):
                        counties = district_info["counties_covered"][:3]
                        self.stdout.write(f"   Counties: {', '.join(counties)}")
                    if district_info.get("zip_codes_covered"):
                        zips = district_info["zip_codes_covered"][:5]
                        self.stdout.write(f"   ZIP Codes: {', '.join(zips)}")

                # Create district
                district = self.create_district(district_info, dry_run)
                if district or dry_run:
                    stats["created"] += 1
                else:
                    stats["skipped"] += 1

                # Progress indicator
                if not dry_run and i % 10 == 0:
                    self.stdout.write(f"Processed {i}/{stats['total']} features...")

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error processing feature {i}: {e}", exc_info=True)
                self.stdout.write(
                    self.style.ERROR(f"Error processing feature {i}: {e}")
                )
                continue

        return stats

    def _display_statistics(self, stats: dict[str, int], dry_run: bool) -> None:
        """
        Display import statistics with colored output.

        Args:
            stats: Dictionary with processing statistics
            dry_run: Whether this was a dry run
        """
        self.stdout.write(f"\n{'=' * 70}")
        self.stdout.write(self.style.SUCCESS("Import Statistics"))
        self.stdout.write(f"{'=' * 70}")
        self.stdout.write(f"Total features:     {stats['total']}")
        self.stdout.write(
            self.style.SUCCESS(f"Created/Would create: {stats['created']}")
        )
        if stats["skipped"] > 0:
            self.stdout.write(
                self.style.WARNING(f"Skipped:          {stats['skipped']}")
            )
        if stats["errors"] > 0:
            self.stdout.write(self.style.ERROR(f"Errors:           {stats['errors']}"))
        self.stdout.write(f"{'=' * 70}\n")

    def _assign_people_to_districts(self) -> None:
        """
        Auto-assign people to imported districts using DistrictAssignmentService.

        This method runs after successful import to automatically create
        PersonDistrict relationships based on voter records, ZIP codes, and counties.
        """
        self.stdout.write(
            self.style.SUCCESS("\nAuto-assigning people to imported districts...")
        )

        try:
            service = DistrictAssignmentService()
            assignment_stats = service.bulk_assign_all()

            self.stdout.write(f"\n{'=' * 70}")
            self.stdout.write(self.style.SUCCESS("Assignment Statistics"))
            self.stdout.write(f"{'=' * 70}")
            self.stdout.write(f"Total people:       {assignment_stats['total']}")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Assigned:           {assignment_stats['assigned']}"
                )
            )
            self.stdout.write(f"Skipped:            {assignment_stats['skipped']}")
            if assignment_stats["errors"] > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"Errors:             {assignment_stats['errors']}"
                    )
                )
            self.stdout.write(f"Via voter record:   {assignment_stats['voter_record']}")
            self.stdout.write(f"Via ZIP code:       {assignment_stats['zip_code']}")
            self.stdout.write(f"Via county:         {assignment_stats['county']}")
            self.stdout.write(f"{'=' * 70}\n")

        except Exception as e:
            logger.error(f"Error during auto-assignment: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Auto-assignment failed: {e}"))
