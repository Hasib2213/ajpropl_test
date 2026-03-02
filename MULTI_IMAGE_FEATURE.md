# Multi-Image Upload Feature Documentation

## Overview

The system now supports **multi-image batch processing** with **per-image feature selection** and **dynamic SKU generation**. This allows users to upload multiple images at once and select different AI features for each image independently.

---

## Feature Highlights

### 1. **Multiple Image Upload**
- Upload up to **20 images per batch**
- Each image processed independently
- Parallel processing for performance

### 2. **Per-Image Feature Selection**
Users can select different features for each image:

**Image 1 Options:**
- Background Removal ✓
- Model ✓
- Physical Dimensions

**Image 2 Options:**
- Physical Dimensions ✓
- Virtual Try-On ✓
- Mannequin

**Image 3+ Options:**
- And so on...

Each image has its own processing pipeline with independently selected features.

### 3. **Dynamic SKU Generation**
Each feature gets a unique SKU with a feature-based suffix:

```
Base SKU: SKU-000123456

Feature Suffix Mapping:
- physical_dimensions      → SKU-000123456_1
- background_removal       → SKU-000123456_2
- ai_virtual_tryon         → SKU-000123456_3
- image_diagram            → SKU-000123456_4
- mannequin                → SKU-000123456_5
- model                    → SKU-000123456_6
```

**Example:**
```json
{
  "image_index": 0,
  "selected_features": ["background_removal", "model"],
  "generated_skus": {
    "background_removal": "SKU-000123456_2",
    "model": "SKU-000123456_6"
  }
}
```

---

## API Endpoints

### **New Endpoint: POST `/api/v1/generate-batch`**

Upload multiple images with per-image feature selection.

#### Request Format

```bash
curl -X POST http://localhost:8000/api/v1/generate-batch \
  -F "seller_id=seller_123" \
  -F "images=@image1.jpg" \
  -F "images=@image2.jpg" \
  -F "images=@image3.jpg" \
  -F "features_json=[
    {\"features\": [\"background_removal\", \"model\"]},
    {\"features\": [\"physical_dimensions\", \"ai_virtual_tryon\"]},
    {\"features\": [\"image_diagram\", \"mannequin\"]}
  ]"
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `seller_id` | String | Unique seller identifier |
| `images` | File[] | Multiple image files (JPG, PNG, WebP) - max 20 |
| `features_json` | String | JSON array of feature selections for each image |

#### Features JSON Format

```json
[
  {
    "features": ["background_removal", "model"]
  },
  {
    "features": ["physical_dimensions", "ai_virtual_tryon"]
  },
  {
    "features": ["image_diagram"]
  }
]
```

**Note:** The number of feature objects must match the number of images.

#### Response

```json
{
  "product_id": "aabbccdd-eeff-1122-3344-556677889900",
  "status": "pending",
  "message": "Batch processing started for 3 images. Poll /status to track progress."
}
```

---

## Database Schema Changes

### **ProductInDB Model**

New fields added to support multi-image:

```python
class ProductInDB(BaseModel):
    id: str  # Product ID
    seller_id: str
    status: ProcessingStatus
    
    # Single image (backward compatibility)
    selected_features: Optional[List[str]] = None
    images: Optional[ImageOutputs] = ImageOutputs()
    
    # Multi-image support (NEW)
    is_multi_image: bool = False
    images_batch: Optional[List[ImageProcessingData]] = []
```

### **ImageProcessingData Model (NEW)**

```python
class ImageProcessingData(BaseModel):
    image_index: int  # 0, 1, 2, ...
    selected_features: List[str]  # ["background_removal", "model"]
    
    # Generated outputs
    original_url: Optional[str] = None
    background_removed_url: Optional[str] = None
    image_diagram_url: Optional[str] = None
    virtual_tryon_urls: Optional[List[str]] = []
    mannequin_urls: Optional[List[str]] = []
    model_urls: Optional[List[str]] = []
    
    # Generated SKUs for each feature
    generated_skus: Optional[Dict[str, str]] = {}
    # Example: {
    #   "background_removal": "SKU-000123456_2",
    #   "model": "SKU-000123456_6"
    # }
    
    dimensions: Optional[PhysicalDimensions] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

---

## Example Workflow

### Step 1: User Uploads 3 Images with Different Features

```bash
POST /api/v1/generate-batch

Images:
- photo1.jpg → features: ["background_removal", "model"]
- photo2.jpg → features: ["physical_dimensions", "ai_virtual_tryon"]
- photo3.jpg → features: ["image_diagram", "mannequin"]
```

### Step 2: Response with Product ID

```json
{
  "product_id": "prod-12345-67890",
  "status": "pending",
  "message": "Batch processing started for 3 images..."
}
```

### Step 3: Poll Status

```bash
GET /api/v1/prod-12345-67890/status
```

**Response (Processing):**
```json
{
  "product_id": "prod-12345-67890",
  "overall_status": "processing",
  "features": [...]
}
```

**Response (Completed):**
```json
{
  "product_id": "prod-12345-67890",
  "overall_status": "completed",
  "product": {
    "is_multi_image": true,
    "images_batch": [
      {
        "image_index": 0,
        "selected_features": ["background_removal", "model"],
        "original_url": "...",
        "background_removed_url": "...",
        "model_urls": ["...", "..."],
        "generated_skus": {
          "background_removal": "SKU-000123456_2",
          "model": "SKU-000123456_6"
        },
        "status": "completed"
      },
      {
        "image_index": 1,
        "selected_features": ["physical_dimensions", "ai_virtual_tryon"],
        "original_url": "...",
        "dimensions": {...},
        "virtual_tryon_urls": ["...", "..."],
        "generated_skus": {
          "physical_dimensions": "SKU-000789abc_1",
          "ai_virtual_tryon": "SKU-000789abc_3"
        },
        "status": "completed"
      },
      ...
    ]
  }
}
```

### Step 4: Get Full Product Data

```bash
GET /api/v1/prod-12345-67890
```

Returns complete product with all processed images and SKUs.

---

## Backend Processing Flow

### **Pipeline: `AIPipeline.run_batch()`**

1. **Validate & Parse**
   - Validate all images (content type, size)
   - Parse feature selections for each image
   - Generate unique base SKUs for each image

2. **Per-Image Processing** (Sequential)
   - For each image:
     - Upload original
     - Remove background (if needed)
     - Run selected features in parallel
     - Save outputs with generated SKUs
     - Update MongoDB with results

3. **Completion**
   - Mark entire batch as `COMPLETED`
   - All images ready for publishing

### **Database Updates**

Each image updates use MongoDB's array indexing:
```
images_batch.0.background_removed_url = "..."
images_batch.0.generated_skus.background_removal = "SKU-000123456_2"
images_batch.1.dimensions = {...}
images_batch.1.generated_skus.physical_dimensions = "SKU-000789abc_1"
```

---

## SKU Generator Utility

### **File:** `utils/sku_generator.py`

#### Functions

```python
# Generate base SKU
generate_base_sku(prefix="SKU") -> str
# Returns: "SKU-000123456"

# Generate feature-specific SKUs for one image
generate_feature_skus(selected_features: List[str]) -> Dict[str, str]
# Returns: {
#   "background_removal": "SKU-000123456_2",
#   "model": "SKU-000123456_6"
# }

# Generate SKUs for entire batch
generate_skus_for_batch(images_batch: List[Dict]) -> Dict[int, Dict[str, str]]
# Returns: {
#   0: {"background_removal": "SKU-000123456_2", "model": "SKU-000123456_6"},
#   1: {"physical_dimensions": "SKU-000789abc_1", ...},
#   ...
# }
```

---

## Backward Compatibility

The system maintains full backward compatibility with the existing single-image API:

```bash
POST /api/v1/generate
- seller_id
- selected_features
- image (single file)
```

Both endpoints work independently. The database schema supports both:
- `is_multi_image = False` → Uses `images` field (single image)
- `is_multi_image = True` → Uses `images_batch` array (multi-image)

---

## Error Handling

### **Common Errors**

| Error | Cause | Solution |
|-------|-------|----------|
| 400 - Image count mismatch | Features count ≠ Images count | Ensure equal counts |
| 400 - Invalid features_json | Malformed JSON | Validate JSON syntax |
| 400 - Too many images | > 20 images in batch | Split into smaller batches |
| 400 - Invalid image format | Non-JPG/PNG/WebP | Use correct image format |
| 500 - Processing failed | AI service error | Check service status, retry |

### **Error Response Example**

```json
{
  "detail": "Image 2: At least one feature must be selected"
}
```

---

## Performance Considerations

### **Processing Speed**

- **Per-image features**: Processed in parallel (3-5 min per image)
- **Batch processing**: Sequential image processing (3-5 min × number of images)
- **Total batch time**: Typically 10-30 minutes for 3-5 images

### **Optimization Tips**

1. Select only necessary features per image
2. Use smaller image files (< 5MB recommended)
3. Don't exceed 20 images per batch
4. Poll status endpoint every 2-3 seconds during processing

### **Storage**

- **Original + Background removed**: ~2MB per image
- **Virtual Try-On/Mannequin/Model**: ~3-5MB per image (multiple samples)
- **Image Diagram**: ~1-2MB per image
- **Total**: ~10-20MB per image (varies by features selected)

---

## Testing

### **Test with cURL**

```bash
# Create test images (3x1px JPG for simplicity)
for i in {1..3}; do
  convert -size 1x1 xc:white test_image_$i.jpg
done

# Upload batch
curl -X POST http://localhost:8000/api/v1/generate-batch \
  -F "seller_id=test_seller" \
  -F "images=@test_image_1.jpg" \
  -F "images=@test_image_2.jpg" \
  -F "images=@test_image_3.jpg" \
  -F "features_json=[
    {\"features\": [\"background_removal\"]},
    {\"features\": [\"physical_dimensions\"]},
    {\"features\": [\"model\"]}
  ]"

# Check status (replace with returned product_id)
curl http://localhost:8000/api/v1/{product_id}/status
```

---

## Summary

The multi-image feature provides:
✅ Upload up to 20 images simultaneously
✅ Select different features for each image
✅ Automatic SKU generation with feature suffixes
✅ Parallel feature processing within each image
✅ Comprehensive status tracking
✅ Full backward compatibility with single-image API

Users can now create diverse product listings with minimal effort!
