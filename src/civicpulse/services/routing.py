"""
Route optimization service for door knocking.

Uses OSRM (Open Source Routing Machine) for road-aware walking routes,
with fallback to distance-based nearest neighbor algorithm.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """A location to visit during door knocking."""

    id: str
    latitude: Decimal
    longitude: Decimal
    address: str
    person_name: str


@dataclass
class OptimizedRoute:
    """Result of route optimization."""

    waypoints: list[Waypoint]  # Ordered list of stops
    total_distance_miles: float
    total_duration_minutes: float
    source: str  # 'osrm' or 'nearest_neighbor'
    geometry: list[tuple[float, float]] | None = None  # Route polyline


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in miles between two points."""
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


class OSRMRoutingService:
    """
    Road-aware route optimization using OSRM Trip API.

    Uses the traveling salesman solver built into OSRM.
    Default uses public demo server; production should use self-hosted.
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or getattr(
            settings, "OSRM_URL", "https://router.project-osrm.org"
        )
        self.timeout = 30  # seconds

    def optimize_route(
        self,
        start_lat: float,
        start_lon: float,
        waypoints: list[Waypoint],
        profile: str = "foot",
    ) -> OptimizedRoute | None:
        """
        Use OSRM /trip endpoint for traveling salesman optimization.

        Args:
            start_lat: Starting latitude (user's current position)
            start_lon: Starting longitude
            waypoints: List of locations to visit
            profile: Routing profile ('foot' for walking, 'car' for driving)

        Returns:
            OptimizedRoute with ordered waypoints, or None if failed
        """
        if not waypoints:
            return None

        # Build coordinates string: start + all waypoints
        coords = f"{start_lon},{start_lat}"
        for wp in waypoints:
            coords += f";{float(wp.longitude)},{float(wp.latitude)}"

        url = f"{self.base_url}/trip/v1/{profile}/{coords}"
        params = {
            "source": "first",  # Start from first coordinate (user location)
            "roundtrip": "false",  # Don't return to start
            "geometries": "geojson",  # Get route geometry
            "overview": "simplified",  # Simplified route line
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "Ok":
                logger.warning(f"OSRM error: {data.get('message', 'Unknown')}")
                return None

            trips = data.get("trips", [])
            if not trips:
                return None

            trip = trips[0]
            legs = trip.get("legs", [])

            # Extract optimized order from waypoint indices
            waypoint_indices = data.get("waypoints", [])
            if len(waypoint_indices) < 2:
                return None

            # Map back to original waypoints (skip first which is user location)
            ordered_waypoints = []
            for wp_data in waypoint_indices[1:]:  # Skip user start location
                original_idx = wp_data.get("waypoint_index", 0) - 1
                if 0 <= original_idx < len(waypoints):
                    ordered_waypoints.append(waypoints[original_idx])

            # Calculate totals
            total_distance_meters = trip.get("distance", 0)
            total_duration_seconds = trip.get("duration", 0)

            # Extract geometry
            geometry = None
            if "geometry" in trip and "coordinates" in trip["geometry"]:
                geometry = [
                    (coord[1], coord[0])  # Convert [lon, lat] to (lat, lon)
                    for coord in trip["geometry"]["coordinates"]
                ]

            return OptimizedRoute(
                waypoints=ordered_waypoints,
                total_distance_miles=total_distance_meters / 1609.34,
                total_duration_minutes=total_duration_seconds / 60,
                source="osrm",
                geometry=geometry,
            )

        except requests.exceptions.Timeout:
            logger.warning("OSRM request timed out")
        except requests.exceptions.RequestException as e:
            logger.warning(f"OSRM request failed: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"OSRM response parsing error: {e}")

        return None


class NearestNeighborRouter:
    """
    Simple nearest neighbor route optimization.

    Fallback when OSRM is unavailable. Uses straight-line distance.
    Good enough for small datasets (<100 waypoints).
    """

    def optimize_route(
        self,
        start_lat: float,
        start_lon: float,
        waypoints: list[Waypoint],
    ) -> OptimizedRoute:
        """
        Greedy nearest neighbor algorithm.

        Starting from user's location, always visit the nearest
        unvisited waypoint next.
        """
        if not waypoints:
            return OptimizedRoute(
                waypoints=[],
                total_distance_miles=0,
                total_duration_minutes=0,
                source="nearest_neighbor",
            )

        remaining = list(waypoints)
        route: list[Waypoint] = []
        total_distance = 0.0
        current_lat, current_lon = start_lat, start_lon

        while remaining:
            # Find nearest waypoint
            min_distance = float("inf")
            nearest_idx = 0

            for i, wp in enumerate(remaining):
                dist = haversine_distance(
                    current_lat, current_lon, float(wp.latitude), float(wp.longitude)
                )
                if dist < min_distance:
                    min_distance = dist
                    nearest_idx = i

            # Move to nearest waypoint
            nearest = remaining.pop(nearest_idx)
            route.append(nearest)
            total_distance += min_distance
            current_lat = float(nearest.latitude)
            current_lon = float(nearest.longitude)

        # Estimate walking time: ~3 mph average walking speed
        walking_speed_mph = 3.0
        total_duration = (total_distance / walking_speed_mph) * 60  # minutes

        return OptimizedRoute(
            waypoints=route,
            total_distance_miles=total_distance,
            total_duration_minutes=total_duration,
            source="nearest_neighbor",
        )


class RouteOptimizer:
    """
    Main route optimization service with caching and fallback.

    Tries OSRM first for road-aware routing, falls back to
    nearest neighbor if OSRM is unavailable.
    """

    CACHE_PREFIX = "route:"
    CACHE_TIMEOUT = 60 * 60  # 1 hour

    def __init__(self, effort_id: str, user_id: int):
        self.effort_id = effort_id
        self.user_id = user_id
        self.osrm = OSRMRoutingService()
        self.fallback = NearestNeighborRouter()

    def _cache_key(self) -> str:
        return f"{self.CACHE_PREFIX}{self.effort_id}:{self.user_id}"

    def get_optimized_route(
        self,
        waypoints: list[Waypoint],
        start_lat: float,
        start_lon: float,
        use_osrm: bool = True,
    ) -> OptimizedRoute:
        """
        Get optimized route, using cache if available.

        Args:
            waypoints: Locations to visit
            start_lat: User's current latitude
            start_lon: User's current longitude
            use_osrm: Whether to try OSRM first (default True)

        Returns:
            OptimizedRoute with ordered waypoints
        """
        if not waypoints:
            return OptimizedRoute(
                waypoints=[],
                total_distance_miles=0,
                total_duration_minutes=0,
                source="empty",
            )

        # Check cache
        cache_key = self._cache_key()
        cached = cache.get(cache_key)

        if cached:
            # Verify cached route still matches current waypoints
            cached_ids = {wp["id"] for wp in cached["waypoints"]}
            current_ids = {wp.id for wp in waypoints}

            if cached_ids == current_ids:
                # Reconstruct OptimizedRoute from cache
                return OptimizedRoute(
                    waypoints=[
                        Waypoint(
                            id=wp["id"],
                            latitude=Decimal(str(wp["latitude"])),
                            longitude=Decimal(str(wp["longitude"])),
                            address=wp["address"],
                            person_name=wp["person_name"],
                        )
                        for wp in cached["waypoints"]
                    ],
                    total_distance_miles=cached["total_distance_miles"],
                    total_duration_minutes=cached["total_duration_minutes"],
                    source=cached["source"],
                )

        # Try OSRM first if enabled
        result = None
        if use_osrm:
            result = self.osrm.optimize_route(start_lat, start_lon, waypoints)

        # Fall back to nearest neighbor
        if result is None:
            result = self.fallback.optimize_route(start_lat, start_lon, waypoints)

        # Cache the result
        cache.set(
            cache_key,
            {
                "waypoints": [
                    {
                        "id": wp.id,
                        "latitude": str(wp.latitude),
                        "longitude": str(wp.longitude),
                        "address": wp.address,
                        "person_name": wp.person_name,
                    }
                    for wp in result.waypoints
                ],
                "total_distance_miles": result.total_distance_miles,
                "total_duration_minutes": result.total_duration_minutes,
                "source": result.source,
            },
            self.CACHE_TIMEOUT,
        )

        return result

    def invalidate_cache(self):
        """Clear cached route (e.g., when assignments change)."""
        cache.delete(self._cache_key())
