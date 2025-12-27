"""
Geocoding service abstraction for CivicPulse.

Provides address-to-coordinate lookup with caching and fallback support.
Primary: OpenCage (2,500 free/day)
Fallback: Nominatim (OpenStreetMap, free but rate-limited)
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass
class GeocodingResult:
    """Result of a geocoding operation."""

    latitude: Decimal
    longitude: Decimal
    formatted_address: str
    confidence: float  # 0-1 scale
    source: str  # 'opencage', 'nominatim', etc.


class GeocodingService(ABC):
    """Abstract base class for geocoding services."""

    @abstractmethod
    def geocode(self, address: str) -> GeocodingResult | None:
        """Geocode a single address."""
        pass


class OpenCageGeocodingService(GeocodingService):
    """OpenCage geocoding implementation."""

    def __init__(self, api_key: str):
        from geopy.geocoders import OpenCage

        self.geocoder = OpenCage(api_key, timeout=10)

    def geocode(self, address: str) -> GeocodingResult | None:
        from geopy.exc import GeocoderServiceError, GeocoderTimedOut

        try:
            location = self.geocoder.geocode(
                address, country_codes="us", no_annotations=True, limit=1
            )
            if location:
                # OpenCage returns confidence 1-10, normalize to 0-1
                raw_confidence = location.raw.get("confidence", 5)
                return GeocodingResult(
                    latitude=Decimal(str(location.latitude)),
                    longitude=Decimal(str(location.longitude)),
                    formatted_address=location.address,
                    confidence=raw_confidence / 10.0,
                    source="opencage",
                )
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning(f"OpenCage geocoding failed: {e}")
        except Exception as e:
            logger.error(f"OpenCage unexpected error: {e}")
        return None


class NominatimGeocodingService(GeocodingService):
    """Nominatim (OpenStreetMap) geocoding implementation."""

    def __init__(self):
        from geopy.geocoders import Nominatim

        self.geocoder = Nominatim(user_agent="civicpulse", timeout=10)

    def geocode(self, address: str) -> GeocodingResult | None:
        from geopy.exc import GeocoderServiceError, GeocoderTimedOut

        try:
            location = self.geocoder.geocode(
                address, country_codes="us", addressdetails=True
            )
            if location:
                return GeocodingResult(
                    latitude=Decimal(str(location.latitude)),
                    longitude=Decimal(str(location.longitude)),
                    formatted_address=location.address,
                    confidence=0.7,  # Nominatim doesn't provide confidence
                    source="nominatim",
                )
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning(f"Nominatim geocoding failed: {e}")
        except Exception as e:
            logger.error(f"Nominatim unexpected error: {e}")
        return None


class CachedGeocodingService:
    """
    Wrapper that adds caching and fallback logic to geocoding services.
    Uses Redis cache (via Django cache framework) for persistent caching.
    """

    CACHE_PREFIX = "geocode:"
    CACHE_TIMEOUT = 60 * 60 * 24 * 30  # 30 days

    def __init__(self):
        self.services: list[GeocodingService] = []
        self._config = getattr(settings, "CIVICPULSE_GEOCODING", {})

        # Try to initialize OpenCage first (if API key provided)
        api_key = self._config.get("OPENCAGE_API_KEY", "")
        if api_key:
            try:
                self.services.append(OpenCageGeocodingService(api_key))
                logger.info("OpenCage geocoding service initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenCage: {e}")

        # Always add Nominatim as fallback
        try:
            self.services.append(NominatimGeocodingService())
            logger.info("Nominatim geocoding service initialized as fallback")
        except Exception as e:
            logger.error(f"Failed to initialize Nominatim: {e}")

        if not self.services:
            logger.error("No geocoding services available!")

    def _cache_key(self, address: str) -> str:
        """Generate cache key for an address."""
        normalized = address.lower().strip()
        address_hash = hashlib.md5(normalized.encode()).hexdigest()
        return f"{self.CACHE_PREFIX}{address_hash}"

    def geocode(self, address: str) -> GeocodingResult | None:
        """
        Geocode an address with caching and fallback.

        1. Check cache first
        2. Try each service in order
        3. Cache successful results
        4. Return None if all services fail
        """
        if not address or not address.strip():
            return None

        cache_key = self._cache_key(address)

        # Check cache
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for: {address[:50]}")
            return GeocodingResult(**cached)

        # Get minimum confidence threshold
        min_confidence = self._config.get("MIN_CONFIDENCE", 0.5)

        # Try each service
        for service in self.services:
            result = service.geocode(address)
            if result and result.confidence >= min_confidence:
                # Cache the result
                cache_timeout = self._config.get("CACHE_TIMEOUT_DAYS", 30) * 86400
                cache.set(
                    cache_key,
                    {
                        "latitude": result.latitude,
                        "longitude": result.longitude,
                        "formatted_address": result.formatted_address,
                        "confidence": result.confidence,
                        "source": result.source,
                    },
                    cache_timeout,
                )
                logger.info(f"Geocoded via {result.source}: {address[:50]}")
                return result

        logger.warning(f"All geocoding services failed for: {address[:50]}")
        return None

    def geocode_address_fields(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
    ) -> GeocodingResult | None:
        """
        Convenience method for geocoding from separate address fields.
        """
        parts = [street]
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if zip_code:
            parts.append(zip_code)
        address = ", ".join(parts)
        return self.geocode(address)

    @property
    def is_available(self) -> bool:
        """Check if any geocoding services are available."""
        return len(self.services) > 0


# Singleton instance for convenience
_geocoder_instance: CachedGeocodingService | None = None


def get_geocoder() -> CachedGeocodingService:
    """Get or create the singleton geocoder instance."""
    global _geocoder_instance
    if _geocoder_instance is None:
        _geocoder_instance = CachedGeocodingService()
    return _geocoder_instance
