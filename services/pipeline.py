"""
AI Pipeline — Main Orchestrator
=================================
User selected features গুলো parallel এ run করে।
Figma → "Generate" button press করলে এই pipeline চলে।

Flow:
  Upload → [Selected Features run in parallel] → Product Listing → Done
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List

from config.database import col_products
from models.product import (
    ProductInDB, SelectedFeature, ProcessingStatus,
    ImageOutputs, ProductDetails, VariantData, StorageAutomation,
)
from services.features import (
    physical_dimensions_service,
    background_removal_service,
    image_diagram_service,
    get_virtual_tryon_service,
    get_mannequin_service,
    get_model_service,
)
from services.product_listing import product_listing_service
from utils.storage import storage


class AIPipeline:

    async def run(
        self,
        product_id: str,
        image_bytes: bytes,
        selected_features: List[SelectedFeature],
    ) -> None:
        """
        Selected features parallel এ চালায়।
        MongoDB তে live update করতে থাকে।
        """
        col = col_products()

        # Mark as processing
        await col.update_one(
            {"_id": product_id},
            {"$set": {"status": ProcessingStatus.PROCESSING, "updated_at": datetime.utcnow()}},
        )

        try:
            # ── Step 1: Upload original image ─────────────────────────────
            original_url = await storage.upload(image_bytes, folder="originals", ext="jpg")
            await self._update(product_id, {"images.original_url": original_url})

            # ── Step 2: Background Removal (needed by other features) ─────
            # Run first — others depend on the clean image
            bg_removed_bytes = None
            bg_removed_url = None

            if SelectedFeature.BACKGROUND_REMOVAL in selected_features:
                print(f"[{product_id}] Running Background Removal...")
                bg_removed_bytes = await background_removal_service.remove_with_white_bg(image_bytes)
                bg_removed_url = await storage.upload(bg_removed_bytes, folder="bg_removed", ext="png")
                await self._update(product_id, {"images.background_removed_url": bg_removed_url})
                print(f"[{product_id}] Background Removal done")
            else:
                # Still remove bg silently for other features to use
                try:
                    bg_removed_bytes = await background_removal_service.remove_with_white_bg(image_bytes)
                    bg_removed_url = await storage.upload(bg_removed_bytes, folder="bg_removed", ext="png")
                except Exception:
                    bg_removed_url = original_url

            # ── Step 3: Run remaining features in PARALLEL ────────────────
            tasks = {}

            if SelectedFeature.PHYSICAL_DIMENSIONS in selected_features:
                tasks["dimensions"] = physical_dimensions_service.extract(image_bytes)

            if SelectedFeature.AI_VIRTUAL_TRYON in selected_features:
                tryon_service = get_virtual_tryon_service()
                if tryon_service is not None:
                    tasks["tryon"] = tryon_service.generate(bg_removed_url, num_samples=1)
                else:
                    print(f"[{product_id}] Try-On skipped (service unavailable)")

            if SelectedFeature.IMAGE_DIAGRAM in selected_features:
                tasks["diagram"] = self._run_diagram(image_bytes, product_id)

            if SelectedFeature.MANNEQUIN in selected_features:
                mannequin_service = get_mannequin_service()
                if mannequin_service is not None:
                    tasks["mannequin"] = mannequin_service.generate_ghost_mannequin(bg_removed_url, num_samples=1)
                else:
                    print(f"[{product_id}] Mannequin skipped (service unavailable)")

            if SelectedFeature.MODEL in selected_features:
                model_service = get_model_service()
                if model_service is not None:
                    tasks["model"] = model_service.generate_on_model(bg_removed_url, num_samples=1)
                else:
                    print(f"[{product_id}] Model skipped (service unavailable)")

            # Always generate product listing
            tasks["listing"] = product_listing_service.generate(image_bytes)

            # Run all in parallel
            print(f"[{product_id}] Running {len(tasks)} tasks in parallel...")
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            result_map = dict(zip(tasks.keys(), results))

            # ── Step 4: Process results & save to MongoDB ─────────────────
            update_data: Dict = {}

            # Prepare details object
            details = {}
            
            # Physical Dimensions
            if "dimensions" in result_map and not isinstance(result_map["dimensions"], Exception):
                dims = result_map["dimensions"]
                update_data["dimensions"] = dims.dict()
                details["dimensions"] = dims.dict()
                print(f"[{product_id}] Dimensions done")
            elif "dimensions" in result_map:
                print(f"[{product_id}] Dimensions failed: {result_map['dimensions']}")

            # Virtual Try-On
            if "tryon" in result_map and not isinstance(result_map["tryon"], Exception):
                tryon_bytes_list = result_map["tryon"]
                tryon_urls = await asyncio.gather(*[storage.upload(b, folder="tryons", ext="png") for b in tryon_bytes_list])
                update_data["images.virtual_tryon_urls"] = list(tryon_urls)
                print(f"[{product_id}] Virtual Try-On done ({len(tryon_urls)} images)")
            elif "tryon" in result_map:
                print(f"[{product_id}] Try-On failed: {result_map['tryon']}")

            # Image Diagram
            if "diagram" in result_map and not isinstance(result_map["diagram"], Exception):
                diagram_url = result_map["diagram"]
                update_data["images.image_diagram_url"] = diagram_url
                print(f"[{product_id}] Image Diagram done")
            elif "diagram" in result_map:
                print(f"[{product_id}] Diagram failed: {result_map['diagram']}")

            # Mannequin
            if "mannequin" in result_map and not isinstance(result_map["mannequin"], Exception):
                mannequin_bytes_list = result_map["mannequin"]
                mannequin_urls = await asyncio.gather(*[storage.upload(b, folder="mannequins", ext="png") for b in mannequin_bytes_list])
                update_data["images.mannequin_urls"] = list(mannequin_urls)
                print(f"[{product_id}] Mannequin done ({len(mannequin_urls)} images)")
            elif "mannequin" in result_map:
                print(f"[{product_id}] Mannequin failed: {result_map['mannequin']}")

            # Model
            if "model" in result_map and not isinstance(result_map["model"], Exception):
                model_bytes_list = result_map["model"]
                model_urls = await asyncio.gather(*[storage.upload(b, folder="models", ext="png") for b in model_bytes_list])
                update_data["images.model_urls"] = list(model_urls)
                print(f"[{product_id}] Model done ({len(model_urls)} images)")
            elif "model" in result_map:
                print(f"[{product_id}] Model failed: {result_map['model']}")

            # Product Listing (Gemini)
            if "listing" in result_map and not isinstance(result_map["listing"], Exception):
                listing = result_map["listing"]
                pd = listing.get("product_details", {})
                vd = listing.get("variant_data", {})

                update_data.update({
                    "product_title":   listing.get("product_title"),
                    "description":     listing.get("description"),
                    "tags":            listing.get("tags", []),
                    "seo_tags":        listing.get("seo_tags", []),
                    "fabric":          listing.get("fabric"),
                    "product_code":    listing.get("product_code"),
                    "care_instructions": listing.get("care_instructions"),
                    "key_features":    listing.get("key_features", []),
                    "product_details": {
                        "category":      pd.get("category"),
                        "brand":         pd.get("brand"),
                        "sleeve_length": pd.get("sleeve_length"),
                        "dress_type":    pd.get("dress_type"),
                        "age_group":     pd.get("age_group"),
                        "gender":        pd.get("gender"),
                    },
                    "variant_data": {
                        "sizes":     vd.get("sizes", []),
                        "colors":    vd.get("colors", []),
                        "condition": vd.get("condition", "New"),
                        "feature":   vd.get("feature"),
                    },
                })
                # Store in details object
                details["listing"] = {
                    "title": listing.get("product_title"),
                    "description": listing.get("description"),
                    "tags": listing.get("tags", []),
                    "fabric": listing.get("fabric"),
                }
                print(f"[{product_id}] Product Listing done")

            # SKU generation
            update_data["sku"] = f"SKU-{uuid.uuid4().hex[:12].upper()}"
            
            # Store details
            update_data["details"] = details

            # Storage & Automation
            update_data["storage"] = {
                "google_drive_folder": "/AutoList/Processed/",
                "auto_listing_enabled": True,
                "last_processed": datetime.utcnow(),
            }

            # Final status
            update_data["status"] = ProcessingStatus.COMPLETED
            update_data["ready_to_publish"] = True
            update_data["updated_at"] = datetime.utcnow()

            await self._update(product_id, update_data)
            print(f"[{product_id}] Pipeline COMPLETE!")

        except Exception as e:
            await col.update_one(
                {"_id": product_id},
                {"$set": {
                    "status": ProcessingStatus.FAILED,
                    "error": str(e),
                    "updated_at": datetime.utcnow(),
                }},
            )
            print(f"[{product_id}] Pipeline FAILED: {e}")
            raise

    async def run_batch(
        self,
        product_id: str,
        image_bytes_list: List[bytes],
        images_batch: List[Dict],
    ) -> None:
        """
        Multi-image batch processing.
        Each image processed independently with its selected features.
        Generated SKUs saved for each feature.
        """
        col = col_products()

        # Mark as processing
        await col.update_one(
            {"_id": product_id},
            {"$set": {"status": ProcessingStatus.PROCESSING, "updated_at": datetime.utcnow()}},
        )

        try:
            # Process each image independently
            for image_data in images_batch:
                image_index = image_data["image_index"]
                selected_features = [SelectedFeature(f) for f in image_data["selected_features"]]
                generated_skus = image_data.get("generated_skus", {})
                image_bytes = image_bytes_list[image_index]

                print(f"[{product_id}] Processing image {image_index + 1} with features: {[f.value for f in selected_features]}")

                # ── Step 1: Upload original image ─────────────────────────────
                original_url = await storage.upload(image_bytes, folder="originals", ext="jpg")
                await self._update_batch_image(product_id, image_index, {"original_url": original_url})

                # ── Step 2: Background Removal ─────────────────────────────────
                bg_removed_bytes = None
                bg_removed_url = None

                if SelectedFeature.BACKGROUND_REMOVAL in selected_features:
                    print(f"[{product_id}:{image_index}] Running Background Removal...")
                    bg_removed_bytes = await background_removal_service.remove_with_white_bg(image_bytes)
                    bg_removed_url = await storage.upload(bg_removed_bytes, folder="bg_removed", ext="png")
                    await self._update_batch_image(product_id, image_index, {"background_removed_url": bg_removed_url})
                    print(f"[{product_id}:{image_index}] Background Removal done")
                else:
                    # Still remove bg silently for other features to use
                    try:
                        bg_removed_bytes = await background_removal_service.remove_with_white_bg(image_bytes)
                        bg_removed_url = await storage.upload(bg_removed_bytes, folder="bg_removed", ext="png")
                    except Exception:
                        bg_removed_url = original_url

                # ── Step 3: Run remaining features in PARALLEL ────────────────
                tasks = {}

                if SelectedFeature.PHYSICAL_DIMENSIONS in selected_features:
                    tasks["dimensions"] = physical_dimensions_service.extract(image_bytes)

                if SelectedFeature.AI_VIRTUAL_TRYON in selected_features:
                    tryon_service = get_virtual_tryon_service()
                    if tryon_service is not None:
                        tasks["tryon"] = tryon_service.generate(bg_removed_url, num_samples=1)
                    else:
                        print(f"[{product_id}:{image_index}] Try-On skipped (service unavailable)")

                if SelectedFeature.IMAGE_DIAGRAM in selected_features:
                    tasks["diagram"] = self._run_diagram(image_bytes, f"{product_id}:{image_index}")

                if SelectedFeature.MANNEQUIN in selected_features:
                    mannequin_service = get_mannequin_service()
                    if mannequin_service is not None:
                        tasks["mannequin"] = mannequin_service.generate_ghost_mannequin(bg_removed_url, num_samples=1)
                    else:
                        print(f"[{product_id}:{image_index}] Mannequin skipped (service unavailable)")

                if SelectedFeature.MODEL in selected_features:
                    model_service = get_model_service()
                    if model_service is not None:
                        tasks["model"] = model_service.generate_on_model(bg_removed_url, num_samples=2)
                    else:
                        print(f"[{product_id}:{image_index}] Model skipped (service unavailable)")

                # Always generate product listing
                tasks["listing"] = product_listing_service.generate(image_bytes)

                # Run all in parallel
                print(f"[{product_id}:{image_index}] Running {len(tasks)} tasks in parallel...")
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                result_map = dict(zip(tasks.keys(), results))

                # ── Step 4: Process results & save to MongoDB ─────────────────
                update_data: Dict = {}

                # Physical Dimensions
                if "dimensions" in result_map and not isinstance(result_map["dimensions"], Exception):
                    dims = result_map["dimensions"]
                    update_data["dimensions"] = dims.dict()
                    print(f"[{product_id}:{image_index}] Dimensions done")
                elif "dimensions" in result_map:
                    print(f"[{product_id}:{image_index}] Dimensions failed: {result_map['dimensions']}")

                # Virtual Try-On
                if "tryon" in result_map and not isinstance(result_map["tryon"], Exception):
                    tryon_bytes_list = result_map["tryon"]
                    tryon_urls = await asyncio.gather(*[storage.upload(b, folder="tryons", ext="png") for b in tryon_bytes_list])
                    update_data["virtual_tryon_urls"] = list(tryon_urls)
                    print(f"[{product_id}:{image_index}] Virtual Try-On done ({len(tryon_urls)} images)")
                elif "tryon" in result_map:
                    print(f"[{product_id}:{image_index}] Try-On failed: {result_map['tryon']}")

                # Image Diagram
                if "diagram" in result_map and not isinstance(result_map["diagram"], Exception):
                    diagram_url = result_map["diagram"]
                    update_data["image_diagram_url"] = diagram_url
                    print(f"[{product_id}:{image_index}] Image Diagram done")
                elif "diagram" in result_map:
                    print(f"[{product_id}:{image_index}] Diagram failed: {result_map['diagram']}")

                # Mannequin
                if "mannequin" in result_map and not isinstance(result_map["mannequin"], Exception):
                    mannequin_bytes_list = result_map["mannequin"]
                    mannequin_urls = await asyncio.gather(*[storage.upload(b, folder="mannequins", ext="png") for b in mannequin_bytes_list])
                    update_data["mannequin_urls"] = list(mannequin_urls)
                    print(f"[{product_id}:{image_index}] Mannequin done ({len(mannequin_urls)} images)")
                elif "mannequin" in result_map:
                    print(f"[{product_id}:{image_index}] Mannequin failed: {result_map['mannequin']}")

                # Model
                if "model" in result_map and not isinstance(result_map["model"], Exception):
                    model_bytes_list = result_map["model"]
                    model_urls = await asyncio.gather(*[storage.upload(b, folder="models", ext="png") for b in model_bytes_list])
                    update_data["model_urls"] = list(model_urls)
                    print(f"[{product_id}:{image_index}] Model done ({len(model_urls)} images)")
                elif "model" in result_map:
                    print(f"[{product_id}:{image_index}] Model failed: {result_map['model']}")

                # Product Listing (Gemini) - only if needed
                if "listing" in result_map and not isinstance(result_map["listing"], Exception):
                    listing = result_map["listing"]
                    pd = listing.get("product_details", {})
                    vd = listing.get("variant_data", {})

                    update_data.update({
                        "product_title": listing.get("product_title"),
                        "description": listing.get("description"),
                        "tags": listing.get("tags", []),
                        "seo_tags": listing.get("seo_tags", []),
                        "fabric": listing.get("fabric"),
                        "product_code": listing.get("product_code"),
                        "care_instructions": listing.get("care_instructions"),
                        "key_features": listing.get("key_features", []),
                        "product_details": {
                            "category": pd.get("category"),
                            "brand": pd.get("brand"),
                            "sleeve_length": pd.get("sleeve_length"),
                            "dress_type": pd.get("dress_type"),
                            "age_group": pd.get("age_group"),
                            "gender": pd.get("gender"),
                        },
                        "variant_data": {
                            "sizes": vd.get("sizes", []),
                            "colors": vd.get("colors", []),
                            "condition": vd.get("condition", "New"),
                            "feature": vd.get("feature"),
                        },
                        "listing": {
                            "title": listing.get("product_title"),
                            "description": listing.get("description"),
                            "tags": listing.get("tags", []),
                            "fabric": listing.get("fabric"),
                        },
                    })
                    print(f"[{product_id}:{image_index}] Product Listing done")
                elif "listing" in result_map:
                    print(f"[{product_id}:{image_index}] Product Listing failed: {result_map['listing']}")

                # Update image with generated data
                update_data["generated_skus"] = generated_skus  # Keep the pre-generated SKUs
                update_data["status"] = ProcessingStatus.COMPLETED
                update_data["updated_at"] = datetime.utcnow()

                await self._update_batch_image(product_id, image_index, update_data)

            # Mark entire batch as completed
            await col.update_one(
                {"_id": product_id},
                {"$set": {
                    "status": ProcessingStatus.COMPLETED,
                    "ready_to_publish": True,
                    "updated_at": datetime.utcnow(),
                }},
            )
            print(f"[{product_id}] Batch Pipeline COMPLETE!")

        except Exception as e:
            await col.update_one(
                {"_id": product_id},
                {"$set": {
                    "status": ProcessingStatus.FAILED,
                    "error": str(e),
                    "updated_at": datetime.utcnow(),
                }},
            )
            print(f"[{product_id}] Batch Pipeline FAILED: {e}")
            raise

    async def _run_diagram(self, image_bytes: bytes, product_id: str) -> str:
        """Image diagram run করে URL return করে (aggressively compressed)"""
        import io
        from PIL import Image
        
        diagram_bytes = await image_diagram_service.generate(image_bytes)
        original_size = len(diagram_bytes) / 1024 / 1024
        
        # Open and prepare image
        img = Image.open(io.BytesIO(diagram_bytes))
        
        # Resize to max 1200px width to reduce size
        max_width = 1200
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to JPEG for much better compression than PNG
        compressed = io.BytesIO()
        img = img.convert("RGB")  # JPEG needs RGB, not RGBA
        img.save(compressed, format="JPEG", quality=90, optimize=True)
        compressed_bytes = compressed.getvalue()
        
        final_size = len(compressed_bytes) / 1024 / 1024
        print(f"Diagram: {original_size:.1f}MB → {final_size:.1f}MB (resized + JPEG quality 90)")
        
        return await storage.upload(compressed_bytes, folder="diagrams", ext="jpg")

    async def _update(self, product_id: str, data: dict):
        """MongoDB তে partial update"""
        await col_products().update_one(
            {"_id": product_id},
            {"$set": data},
        )

    async def _update_batch_image(self, product_id: str, image_index: int, data: dict):
        """MongoDB এ batch image এর জন্য partial update"""
        update_dict = {}
        for key, value in data.items():
            update_dict[f"images_batch.{image_index}.{key}"] = value
        
        await col_products().update_one(
            {"_id": product_id},
            {"$set": update_dict},
        )


ai_pipeline = AIPipeline()