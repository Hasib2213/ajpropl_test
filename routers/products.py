from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form, Response
from typing import Optional, List
from datetime import datetime
import uuid
import json

from config.database import col_products
from models.product import (
    SelectedFeature, ProcessingStatus,
    ProductResponse, ProcessingStatusResponse, FeatureStatusItem,
    ImageProcessingData,
)
from services.pipeline import AIPipeline
from utils.storage import storage
from utils.sku_generator import generate_skus_for_batch

router = APIRouter(tags=["Products"])

ALLOWED_FEATURES = [f.value for f in SelectedFeature]
ai_pipeline = AIPipeline()


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/generate
# Figma → "Generate" button - Upload image & select AI features
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/generate", response_model=ProductResponse)
async def generate(
    background_tasks: BackgroundTasks,
    seller_id: str = Form(...),
    selected_features: str = Form(...),     # JSON array string: ["background_removal","model"]
    image: UploadFile = File(...),
):
    """
    Figma → User image upload + features select → Generate button।
    
    **Request:**
    - `seller_id`: Unique seller identifier
    - `selected_features`: JSON array of feature names
    - `image`: Garment photo (JPG/PNG/WebP)
    
    **Example:**
    ```
    POST /api/v1/generate
    seller_id: "seller_123"
    selected_features: '["physical_dimensions","background_removal","model"]'
    image: <file>
    ```
    
    **Response:** Returns product_id immediately — processing runs in background.
    Poll `/api/v1/{id}/status` to check progress.
    """
    # Validate image
    if image.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif", "image/tiff", "image/avif"):
        raise HTTPException(400, f"Only JPG, PNG, WebP, GIF, HEIC, HEIF, TIFF, AVIF images allowed. Got: {image.content_type}")

    # Parse selected features (supports JSON list, comma list, or "all")
    try:
        normalized = selected_features.strip()
        if normalized.lower() in ("all", "*"):
            feature_list_raw = ALLOWED_FEATURES
        else:
            try:
                feature_list_raw = json.loads(normalized)
            except json.JSONDecodeError:
                feature_list_raw = [f.strip() for f in normalized.split(",") if f.strip()]

        # Keep order, drop duplicates, validate
        seen = set()
        feature_list = []
        for f in feature_list_raw:
            if f in ALLOWED_FEATURES and f not in seen:
                feature_list.append(SelectedFeature(f))
                seen.add(f)
    except Exception:
        raise HTTPException(400, f"Invalid features. Valid options: {ALLOWED_FEATURES}")

    if not feature_list:
        raise HTTPException(400, "At least one feature must be selected")

    # Read image
    image_bytes = await image.read()

    # Create product document in MongoDB
    product_id = str(uuid.uuid4())
    doc = {
        "_id": product_id,
        "seller_id": seller_id,
        "status": ProcessingStatus.PENDING,
        "selected_features": [f.value for f in feature_list],
        "images": {},
        "details": {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await col_products().insert_one(doc)

    # Run AI pipeline in background
    background_tasks.add_task(
        ai_pipeline.run,
        product_id,
        image_bytes,
        feature_list,
    )

    return ProductResponse(
        product_id=product_id,
        status=ProcessingStatus.PENDING,
        message="Processing started. Poll /status to track progress.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/generate-batch
# Multi-image upload with per-image feature selection
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/generate-batch", response_model=ProductResponse)
async def generate_batch(
    background_tasks: BackgroundTasks,
    seller_id: str = Form(..., description="Unique seller identifier"),
    features_json: str = Form(..., description='JSON array: [{"features":["bg_removal","model"]}, ...]'),
    images: List[UploadFile] = File(..., description="Multiple garment photos (JPG/PNG/WebP)")
):
    """
    Multi-image upload with per-image feature selection.
    
    ⚠️ **Note for Swagger UI users:** 
    Due to OpenAPI 3.0 limitations, Swagger UI may not properly render the multiple file upload field.
    Please use one of these alternatives:
    - **Postman** (recommended for testing)
    - **HTML Form** (see test_multi_upload.html in project root)
    - **cURL** command
    - **JavaScript fetch/axios**
    
    **Request (multipart/form-data):**
    - `seller_id`: Unique seller identifier
    - `features_json`: JSON array where each object contains "features" for that image
    - `images`: Multiple garment photos (JPG/PNG/WebP) - actual file uploads
    
    **Example:**
    ```
    POST /api/v1/generate-batch
    Content-Type: multipart/form-data
    
    seller_id: "seller_123"
    features_json: '[{"features": ["background_removal", "model"]}, {"features": ["physical_dimensions", "virtual_tryon"]}]'
    images: <file1.jpg>
    images: <file2.jpg>
    images: <file3.jpg>
    ```
    
    **Response:** Returns batch product_id immediately — processing runs in background.
    Each image is processed independently with its selected features.
    Generated SKUs format: SKU-000123456_1 (suffix depends on feature: 1=physical_dimensions, 2=background_removal, etc.)
    """
    
    # ─── FILE INPUT VALIDATION ───
    # Validate image count
    if not images or len(images) == 0:
        raise HTTPException(400, "At least one image must be provided")
    
    if len(images) > 20:
        raise HTTPException(400, "Maximum 20 images allowed per batch")
    
    print(f"[BATCH] Received {len(images)} images from {seller_id}")
    
    # Process uploaded files
    image_bytes_list = []
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max per image
    ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif", "image/tiff", "image/avif")
    
    for idx, upload_file in enumerate(images):
        try:
            # Validate content type
            if upload_file.content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    400, 
                    f"Image {idx + 1} ({upload_file.filename}): Invalid type '{upload_file.content_type}'. Only JPG, PNG, WebP, GIF, HEIC, HEIF, TIFF, AVIF allowed."
                )
            
            # Read file bytes
            img_bytes = await upload_file.read()
            
            # Check file size
            if len(img_bytes) == 0:
                raise HTTPException(400, f"Image {idx + 1} ({upload_file.filename}): File is empty")
            
            if len(img_bytes) > MAX_FILE_SIZE:
                raise HTTPException(
                    400, 
                    f"Image {idx + 1} ({upload_file.filename}): Size ({len(img_bytes) / 1024 / 1024:.1f}MB) exceeds 50MB limit"
                )
            
            image_bytes_list.append(img_bytes)
            file_size_kb = len(img_bytes) / 1024
            print(f"  ✓ Image {idx + 1}: {upload_file.filename} ({file_size_kb:.1f}KB)")
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Image {idx + 1}: Failed to read file - {str(e)}")
    
    # ─── FEATURES VALIDATION ───
    # Parse features JSON
    try:
        features_data = json.loads(features_json.strip())
        if not isinstance(features_data, list):
            raise ValueError("features_json must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(400, f"Invalid features_json: {str(e)}")
    
    # Validate feature count matches image count
    if len(features_data) != len(images):
        raise HTTPException(
            400,
            f"Number of feature sets ({len(features_data)}) must match number of images ({len(images)})"
        )
    
    # Validate and normalize features for each image
    images_batch = []
    for idx, (features_spec, img_bytes) in enumerate(zip(features_data, image_bytes_list)):
        features_raw = features_spec.get("features", [])
        
        if not features_raw:
            raise HTTPException(400, f"Image {idx}: At least one feature must be selected")
        
        # Validate and normalize
        try:
            normalized = features_raw
            if isinstance(features_raw, str):
                normalized = json.loads(features_raw) if features_raw.startswith("[") else [features_raw]
            
            # Keep order, drop duplicates, validate
            seen = set()
            feature_list = []
            for f in normalized:
                if f in ALLOWED_FEATURES and f not in seen:
                    feature_list.append(f)
                    seen.add(f)
            
            if not feature_list:
                raise HTTPException(400, f"Image {idx}: Invalid features. Valid options: {ALLOWED_FEATURES}")
        except Exception as e:
            raise HTTPException(400, f"Image {idx}: Feature validation failed: {str(e)}")
        
        # Create image batch entry
        images_batch.append({
            "image_index": idx,
            "selected_features": feature_list,
        })
    
    # Generate SKUs for all images
    batch_skus = generate_skus_for_batch(images_batch)
    
    # Create product document in MongoDB
    product_id = str(uuid.uuid4())
    
    # Prepare images_batch with SKU data
    images_batch_with_skus = []
    for image_data in images_batch:
        image_data["generated_skus"] = batch_skus[image_data["image_index"]]
        images_batch_with_skus.append(image_data)
    
    doc = {
        "_id": product_id,
        "seller_id": seller_id,
        "status": ProcessingStatus.PENDING,
        "is_multi_image": True,
        "images_batch": images_batch_with_skus,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await col_products().insert_one(doc)
    
    # Run AI pipeline in background for each image
    background_tasks.add_task(
        ai_pipeline.run_batch,
        product_id,
        image_bytes_list,
        images_batch_with_skus,
    )
    
    return ProductResponse(
        product_id=product_id,
        status=ProcessingStatus.PENDING,
        message=f"Batch processing started for {len(images)} images. Poll /status to track progress.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/{product_id}/status
# Poll progress while features are processing
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/{product_id}/status", response_model=ProcessingStatusResponse)
async def get_status(product_id: str):
    """
    Check processing progress for a product.
    
    Figma step 3 (loading animation) polls this endpoint every 1-2 seconds.
    
    **Response includes:**
    - `overall_status`: pending, processing, completed, or failed
    - `features`: List of individual feature statuses + output URLs
    - `product`: Full product data (only when completed)
    
    **Example Response:**
    ```json
    {
      "product_id": "abc123",
      "overall_status": "processing",
      "features": [
        {
          "feature": "background_removal",
          "status": "completed",
          "output_url": "https://..."
        },
        {
          "feature": "model",
          "status": "processing",
          "output_url": null
        }
      ],
      "product": null
    }
    ```
    """
    product = await col_products().find_one({"_id": product_id})
    if not product:
        raise HTTPException(404, "Product not found")

    images = product.get("images", {})
    selected = product.get("selected_features", [])
    overall = product.get("status", ProcessingStatus.PENDING)

    # Build per-feature status
    feature_statuses = []
    feature_output_map = {
        SelectedFeature.BACKGROUND_REMOVAL.value:  images.get("background_removed_url"),
        SelectedFeature.AI_VIRTUAL_TRYON.value:    (images.get("virtual_tryon_urls") or [None])[0],
        SelectedFeature.IMAGE_DIAGRAM.value:       images.get("image_diagram_url"),
        SelectedFeature.MANNEQUIN.value:           (images.get("mannequin_urls") or [None])[0],
        SelectedFeature.MODEL.value:               (images.get("model_urls") or [None])[0],
        SelectedFeature.PHYSICAL_DIMENSIONS.value: None,
    }

    for f in selected:
        try:
            feature_enum = SelectedFeature(f)
        except ValueError:
            continue
        
        output = feature_output_map.get(f)
        if overall == ProcessingStatus.COMPLETED:
            status = ProcessingStatus.COMPLETED
        elif overall == ProcessingStatus.FAILED:
            status = ProcessingStatus.FAILED
        elif output:
            status = ProcessingStatus.COMPLETED
        else:
            status = ProcessingStatus.PROCESSING

        feature_statuses.append(FeatureStatusItem(
            feature=feature_enum,
            status=status,
            output_url=output,
        ))

    # Attach full product if completed
    full_product = None
    if overall == ProcessingStatus.COMPLETED:
        product["id"] = product.pop("_id")
        full_product = product

    return ProcessingStatusResponse(
        product_id=product_id,
        overall_status=overall,
        features=feature_statuses,
        product=full_product,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/{product_id}
# Full product data - Figma Image 6 (Product Listing Preview)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/{product_id}")
async def get_product(product_id: str):
    """
    Get complete product data including all AI-generated content.
    
    Figma Image 6 — Full Product Listing Preview page with:
    - Product images (original, background removed, diagrams, models, try-ons)
    - Physical dimensions (chest, waist, sleeve length, etc.)
    - Auto-generated title, description, tags
    - Variants, SKU, pricing info
    """
    product = await col_products().find_one({"_id": product_id})
    if not product:
        raise HTTPException(404, "Product not found")
    product["id"] = product.pop("_id")
    return product


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/{product_id}
# Seller manual edits before publishing
# ─────────────────────────────────────────────────────────────────────────────
@router.patch("/{product_id}")
async def update_product(product_id: str, update: dict):
    """
    Figma Step 3 — Seller manually edits AI outputs before publishing.
    
    Accepts partial updates. Any field can be edited:
    - title, description
    - dimensions, measurements
    - price, sku, variants
    - tags, condition, material, color
    
    **Example:**
    ```json
    {
      "title": "Beautiful Vintage Leather Jacket",
      "price": 45.99,
      "condition": "like new"
    }
    ```
    """
    product = await col_products().find_one({"_id": product_id})
    if not product:
        raise HTTPException(404, "Product not found")

    update["updated_at"] = datetime.utcnow()
    await col_products().update_one({"_id": product_id}, {"$set": update})
    return {"product_id": product_id, "updated": True, "message": "Product updated successfully"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/{product_id}/publish
# Mark as ready for publishing to marketplace
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{product_id}/publish")
async def publish_product(
    product_id: str,
    price: Optional[float] = None,
    sku: Optional[str] = None
):
    """
    Figma → Seller clicks Download or Save to Drive → marks as published.
    
    Marks product as ready for listing on marketplace.
    Optional: Set price and SKU at publishing time.
    
    **Example:**
    ```
    POST /api/v1/abc123/publish?price=49.99&sku=JACKET-001
    ```
    """
    product = await col_products().find_one({"_id": product_id})
    if not product:
        raise HTTPException(404, "Product not found")

    if product.get("status") != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "Product processing not complete yet")

    update = {
        "ready_to_publish": True,
        "updated_at": datetime.utcnow(),
    }
    if price is not None:
        update["price"] = price
    if sku is not None:
        update["sku"] = sku

    await col_products().update_one({"_id": product_id}, {"$set": update})
    return {
        "product_id": product_id,
        "published": True,
        "message": "Product ready for listing",
        "price": price,
        "sku": sku
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/seller/{seller_id}
# Get all products for a specific seller
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/seller/{seller_id}")
async def get_seller_products(seller_id: str, limit: int = 20, skip: int = 0):
    """
    Retrieve all products for a seller with pagination.
    
    **Query Parameters:**
    - `limit`: Number of products to return (default: 20, max: 100)
    - `skip`: Number of products to skip (default: 0)
    
    **Returns:** List of products sorted by creation date (newest first)
    """
    cursor = col_products().find({"seller_id": seller_id}).skip(skip).limit(limit).sort("created_at", -1)
    products = []
    async for p in cursor:
        p["id"] = p.pop("_id")
        products.append(p)
    return {
        "seller_id": seller_id,
        "products": products,
        "count": len(products),
        "skip": skip,
        "limit": limit
    }


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/v1/{product_id}
# Delete a product
# ─────────────────────────────────────────────────────────────────────────────
@router.delete("/{product_id}")
async def delete_product(product_id: str):
    """
    Permanently delete a product and its associated data.
    
    **Warning:** This action cannot be undone.
    """
    result = await col_products().delete_one({"_id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Product not found")
    return {
        "deleted": True,
        "product_id": product_id,
        "message": "Product deleted successfully"
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/files/{file_id}
# Download/View files stored in MongoDB
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/files/{file_id:path}")
async def download_file(file_id: str):
    """
    Download or view a file from MongoDB storage.
    
    **Usage:**
    - Direct ID: http://localhost:8000/api/v1/files/8a09f3b8-ecae-4e10-89f2-b7779c76f3d4
    - Full URL: http://localhost:8000/api/v1/files/mongodb://8a09f3b8-ecae-4e10-89f2-b7779c76f3d4
    
    **Returns:** Image file (PNG/JPG) as binary response
    """
    # Strip "mongodb://" prefix if present
    if file_id.startswith("mongodb://"):
        file_id = file_id.replace("mongodb://", "")
    
    try:
        file_bytes = await storage.get_file(file_id)
        
        # Detect content type from file bytes
        content_type = "image/png"
        if file_bytes[:2] == b'\xff\xd8':
            content_type = "image/jpeg"
        elif file_bytes[:4] == b'GIF8':
            content_type = "image/gif"
        
        return Response(content=file_bytes, media_type=content_type)
    except FileNotFoundError:
        raise HTTPException(404, f"File {file_id} not found")
