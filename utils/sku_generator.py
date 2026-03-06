"""
SKU Generator - Generate unique SKUs for multi-image with sequential feature suffixes
===================================================================================

For multi-image processing, each feature gets a unique SKU with sequential suffix based on selection order:
Image1 with features [background_remove, model, ai_virtual_tryon]:
  - background_remove → 00012356_1
  - model → 00012356_2
  - ai_virtual_tryon → 00012356_3

Image2 with features [model, physical_dimensions, ai_virtual_tryon]:
  - model → 00234_1
  - physical_dimensions → 00234_2
  - ai_virtual_tryon → 00234_3
"""

import uuid
from typing import Dict, List
from models.product import SelectedFeature


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
    Generate SKUs for each feature with sequential suffix based on selection order.
    
    Args:
        selected_features: List of feature names in order (e.g., ["background_removal", "model", "ai_virtual_tryon"])
        base_sku: Base SKU string. If None, generates new one.
    
    Returns:
        Dict mapping feature -> sku with sequential suffix (e.g., {"background_removal": "SKU-000123456_1", "model": "SKU-000123456_2", "ai_virtual_tryon": "SKU-000123456_3"})
    
    Example:
        >>> skus = generate_feature_skus(["background_removal", "model", "ai_virtual_tryon"])
        >>> skus
        {
            "background_removal": "SKU-000123456_1",
            "model": "SKU-000123456_2",
            "ai_virtual_tryon": "SKU-000123456_3"
        }
    """
    if base_sku is None:
        base_sku = generate_base_sku()
    
    feature_skus = {}
    
    # Assign sequential number to each feature based on order
    for index, feature in enumerate(selected_features, start=1):
        sku = f"{base_sku}_{index}"
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
        "SKU-000123456_1"
        >>> skus[1]["ai_virtual_tryon"]
        "SKU-000789abc_2"
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


def generate_sku_for_feature(base_sku: str, feature_index: int) -> str:
    """
    Generate SKU for a specific feature with sequential index.
    
    Args:
        base_sku: Base SKU string
        feature_index: Sequential index of the feature (1-based)
    
    Returns:
        SKU string with sequential suffix (e.g., "SKU-000123456_1")
    """
    return f"{base_sku}_{feature_index}"
