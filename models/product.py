from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime


# ────────────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────────────
class SelectedFeature(str, Enum):
    PHYSICAL_DIMENSIONS = "physical_dimensions"
    BACKGROUND_REMOVAL = "background_removal"
    AI_VIRTUAL_TRYON = "ai_virtual_tryon"
    IMAGE_DIAGRAM = "image_diagram"
    MANNEQUIN = "mannequin"
    MODEL = "model"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ────────────────────────────────────────────────────────────────────────────
# Physical Dimensions Model
# ────────────────────────────────────────────────────────────────────────────
class PhysicalDimensions(BaseModel):
    chest_width_in: Optional[float] = None
    waist_width_in: Optional[float] = None
    back_length_in: Optional[float] = None
    sleeve_length_in: Optional[float] = None
    under_bust_in: Optional[float] = None
    dress_length_in: Optional[float] = None
    available_sizes: Optional[List[str]] = None
    size_guide: Optional[str] = None
    has_ruler_reference: Optional[bool] = None
    confidence: Optional[str] = None


# ────────────────────────────────────────────────────────────────────────────
# Image Outputs (Single Image)
# ────────────────────────────────────────────────────────────────────────────
class ImageOutputs(BaseModel):
    original_url: Optional[str] = None
    background_removed_url: Optional[str] = None
    image_diagram_url: Optional[str] = None
    virtual_tryon_urls: Optional[List[str]] = []
    mannequin_urls: Optional[List[str]] = []
    model_urls: Optional[List[str]] = []


# ────────────────────────────────────────────────────────────────────────────
# Per-Image Processing Data (Multi-Image Support)
# ────────────────────────────────────────────────────────────────────────────
class ImageProcessingData(BaseModel):
    """Data for each image in a multi-image batch"""
    image_index: int
    selected_features: List[str]
    original_url: Optional[str] = None
    background_removed_url: Optional[str] = None
    image_diagram_url: Optional[str] = None
    virtual_tryon_urls: Optional[List[str]] = []
    mannequin_urls: Optional[List[str]] = []
    model_urls: Optional[List[str]] = []
    dimensions: Optional[PhysicalDimensions] = None
    generated_skus: Optional[Dict[str, str]] = {}  # feature -> sku mapping
    status: ProcessingStatus = ProcessingStatus.PENDING
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ────────────────────────────────────────────────────────────────────────────
# Product Details
# ────────────────────────────────────────────────────────────────────────────
class ProductDetails(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    garment_type: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    condition: Optional[str] = None
    dimensions: Optional[PhysicalDimensions] = None


# ────────────────────────────────────────────────────────────────────────────
# Variant Data
# ────────────────────────────────────────────────────────────────────────────
class VariantData(BaseModel):
    size: Optional[str] = None
    color: Optional[str] = None
    sku: Optional[str] = None


# ────────────────────────────────────────────────────────────────────────────
# Storage & Automation
# ────────────────────────────────────────────────────────────────────────────
class StorageAutomation(BaseModel):
    save_location: Optional[str] = None  # "local" | "cloud"
    auto_publish: Optional[bool] = False
    inventory_sync: Optional[bool] = False


# ────────────────────────────────────────────────────────────────────────────
# Database Models
# ────────────────────────────────────────────────────────────────────────────
class ProductInDB(BaseModel):
    id: str = Field(alias="_id")
    seller_id: str
    status: ProcessingStatus
    # Single image (legacy support)
    selected_features: Optional[List[str]] = None
    images: Optional[ImageOutputs] = ImageOutputs()
    # Multi-image support
    is_multi_image: bool = False
    images_batch: Optional[List[ImageProcessingData]] = []
    # Common fields
    details: Optional[ProductDetails] = ProductDetails()
    variants: Optional[List[VariantData]] = []
    storage: Optional[StorageAutomation] = StorageAutomation()
    price: Optional[float] = None
    sku: Optional[str] = None
    ready_to_publish: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


# ────────────────────────────────────────────────────────────────────────────
# Response Models
# ────────────────────────────────────────────────────────────────────────────
class FeatureStatusItem(BaseModel):
    feature: SelectedFeature
    status: ProcessingStatus
    output_url: Optional[str] = None


class ProductResponse(BaseModel):
    product_id: str
    status: ProcessingStatus
    message: str


class ProcessingStatusResponse(BaseModel):
    product_id: str
    overall_status: ProcessingStatus
    features: List[FeatureStatusItem]
    product: Optional[Dict[str, Any]] = None
