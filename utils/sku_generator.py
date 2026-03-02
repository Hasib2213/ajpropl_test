"""
SKU Generator - Generate unique SKUs for multi-image with feature-based suffixes
================================================================================

For multi-image processing, each feature gets a unique SKU with feature suffix:
- physical_dimensions → 000123456_1
- background_removal → 000123456_2
- ai_virtual_tryon → 000123456_3
- image_diagram → 000123456_4
- mannequin → 000123456_5
- model → 000123456_6
"""

import uuid
from typing import Dict, List
from models.product import SelectedFeature


# Feature to suffix mapping
FEATURE_SUFFIX_MAP = {
    SelectedFeature.PHYSICAL_DIMENSIONS.value: "1",
    SelectedFeature.BACKGROUND_REMOVAL.value: "2",
    SelectedFeature.AI_VIRTUAL_TRYON.value: "3",
    SelectedFeature.IMAGE_DIAGRAM.value: "4",
    SelectedFeature.MANNEQUIN.value: "5",
    SelectedFeature.MODEL.value: "6",
}


def generate_base_sku(prefix: str = "SKU") -> str:
    """
    Generate base SKU (e.g., SKU-000123456)
    
    Args:
        prefix: SKU prefix (default: "SKU")
    
    Returns:
        Base SKU string
    """
    hex_part = uuid.uuid4().hex[:9].upper()  # 9 hex chars
    # Pad with zeros to make 12 chars
    numeric_part = "000" + hex_part[-9:]
    return f"{prefix}-{numeric_part}"


def generate_feature_skus(
    selected_features: List[str],
    base_sku: str = None,
) -> Dict[str, str]:
    """
    Generate SKUs for each feature with suffix.
    
    Args:
        selected_features: List of feature names (e.g., ["background_removal", "physical_dimensions"])
        base_sku: Base SKU string. If None, generates new one.
    
    Returns:
        Dict mapping feature -> sku (e.g., {"background_removal": "SKU-000123456_2", "physical_dimensions": "SKU-000123456_1"})
    
    Example:
        >>> skus = generate_feature_skus(["background_removal", "physical_dimensions"])
        >>> skus
        {
            "physical_dimensions": "SKU-000123456_1",
            "background_removal": "SKU-000123456_2"
        }
    """
    if base_sku is None:
        base_sku = generate_base_sku()
    
    feature_skus = {}
    
    for feature in selected_features:
        # Get suffix for this feature
        suffix = FEATURE_SUFFIX_MAP.get(feature, "9")
        sku = f"{base_sku}_{suffix}"
        feature_skus[feature] = sku
    
    return feature_skus


def generate_skus_for_batch(
    images_batch: List[Dict],
) -> Dict[int, Dict[str, str]]:
    """
    Generate SKUs for each image in a batch.
    
    Args:
        images_batch: List of image processing data dicts with 'selected_features' key
    
    Returns:
        Dict mapping image_index -> {feature -> sku}
    
    Example:
        >>> batch = [
        ...     {"image_index": 0, "selected_features": ["background_removal", "physical_dimensions"]},
        ...     {"image_index": 1, "selected_features": ["ai_virtual_tryon", "model"]},
        ... ]
        >>> skus = generate_skus_for_batch(batch)
        >>> skus[0]["background_removal"]
        "SKU-000123456_2"
        >>> skus[1]["ai_virtual_tryon"]
        "SKU-000789abc_3"
    """
    batch_skus = {}
    
    for image_data in images_batch:
        image_index = image_data.get("image_index", 0)
        selected_features = image_data.get("selected_features", [])
        
        # Generate unique base SKU for each image
        base_sku = generate_base_sku()
        
        # Generate feature-specific SKUs
        feature_skus = generate_feature_skus(selected_features, base_sku)
        
        batch_skus[image_index] = feature_skus
    
    return batch_skus


def get_feature_suffix(feature: str) -> str:
    """
    Get the suffix number for a feature.
    
    Args:
        feature: Feature name (e.g., "background_removal")
    
    Returns:
        Suffix number as string
    """
    return FEATURE_SUFFIX_MAP.get(feature, "9")
