"""
Input validation functions for the Physician Locator backend.
Validates coordinates, radius, descriptions, and other user inputs.
"""

import json
from typing import List, Tuple
from config import cfg
from utils.helpers import sanitise


def validate_lat_lng(lat, lng) -> Tuple[float, float]:
    """
    Validate latitude and longitude coordinates.
    
    Args:
        lat: Latitude value
        lng: Longitude value
        
    Returns:
        Tuple of (latitude, longitude)
        
    Raises:
        TypeError: If values cannot be converted to float
        ValueError: If coordinates are out of valid US range
    """
    lat, lng = float(lat), float(lng)
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise ValueError("Coordinates out of range")
    if not (18.0 <= lat <= 72.0) or not (-180.0 <= lng <= -65.0):
        raise ValueError("Coordinates outside the United States")
    return lat, lng


def validate_radius(radius_str) -> float:
    """
    Validate search radius value.
    
    Args:
        radius_str: Radius as string (in miles)
        
    Returns:
        Validated radius as float
        
    Raises:
        TypeError: If value cannot be converted to float
        ValueError: If radius is out of valid range
    """
    r = float(radius_str)
    if r <= 0 or r > cfg.MAX_RADIUS:
        raise ValueError(f"Radius must be between 1 and {cfg.MAX_RADIUS} miles")
    return r


def validate_descriptions(raw: str, single: str) -> List[str]:
    """
    Validate medical specialty descriptions.
    
    Args:
        raw: JSON string of descriptions
        single: Single description string (fallback)
        
    Returns:
        List of validated description strings
    """
    descriptions: List[str] = []
    if raw:
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("descriptions must be a JSON array")
            descriptions = [
                sanitise(str(d), cfg.MAX_DESC_LEN)
                for d in parsed
                if sanitise(str(d), cfg.MAX_DESC_LEN)
            ]
        except json.JSONDecodeError:
            v = sanitise(raw, cfg.MAX_DESC_LEN)
            descriptions = [v] if v else []
    elif single:
        v = sanitise(single, cfg.MAX_DESC_LEN)
        if v:
            descriptions = [v]
    return descriptions[:cfg.MAX_DESC_COUNT]
