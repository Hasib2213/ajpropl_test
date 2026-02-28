"""
AI Feature Services
===================
Each service handles one AI feature:
1. Physical Dimensions - Measure garment from flat-lay images
2. Background Removal - Remove background from product photos
3. Image Diagram - Create technical diagrams with annotations
4. Virtual Try-On - Generate try-on images on different body types
5. Mannequin - Generate professional mannequin images
6. Model - Generate model try-on images
"""

from services.features.physical_dimensions import PhysicalDimensionsService
from services.features.background_removal import BackgroundRemovalService
from services.features.image_diagram import ImageDiagramService

# Initialize service instances that don't depend on replicate (Python 3.14 incompatible)
physical_dimensions_service = PhysicalDimensionsService()
background_removal_service = BackgroundRemovalService()
image_diagram_service = ImageDiagramService()

# Lazy-load replicate services to avoid Python 3.14 compatibility issues
_virtual_tryon_service = None
_mannequin_service = None
_model_service = None
_virtual_tryon_failed = False
_mannequin_failed = False
_model_failed = False

def get_virtual_tryon_service():
    global _virtual_tryon_service
    global _virtual_tryon_failed
    if _virtual_tryon_failed:
        return None
    if _virtual_tryon_service is None:
        try:
            from services.features.virtual_tryon import VirtualTryOnService
            _virtual_tryon_service = VirtualTryOnService()
        except Exception:
            _virtual_tryon_failed = True
            return None
    return _virtual_tryon_service

def get_mannequin_service():
    global _mannequin_service
    global _mannequin_failed
    if _mannequin_failed:
        return None
    if _mannequin_service is None:
        try:
            from services.features.mannequin import MannequinService
            _mannequin_service = MannequinService()
        except Exception:
            _mannequin_failed = True
            return None
    return _mannequin_service

def get_model_service():
    global _model_service
    global _model_failed
    if _model_failed:
        return None
    if _model_service is None:
        try:
            from services.features.model import ModelService
            _model_service = ModelService()
        except Exception:
            _model_failed = True
            return None
    return _model_service

# Default to None for compatibility
virtual_tryon_service = None
mannequin_service = None
model_service = None

__all__ = [
    'physical_dimensions_service',
    'background_removal_service',
    'image_diagram_service',
    'get_virtual_tryon_service',
    'get_mannequin_service',
    'get_model_service',
]
