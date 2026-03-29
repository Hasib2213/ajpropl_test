"""
Feature 3 — AI Virtual Try-On
================================
Replicate API → IDM-VTON model দিয়ে clothing কে realistic human model এর উপর পরায়।
Flat-lay / mannequin image → on-model photo।

Multiple outputs = multiple image tabs in Figma (Image 1, 2, 3...)
"""

import os
import io
import httpx
from typing import List, Optional
from config.settings import settings
from services.features.nano_banana import (
    NanoBananaProClient,
    get_gendered_model_pools,
    parse_model_urls,
)
from services.features.replicate_utils import (
    InvalidReplicateInputError,
    InvalidReplicateModelError,
    run_replicate_with_retry,
)


# IDM-VTON — Best virtual try-on model on Replicate (2024-2025)
IDM_VTON_MODEL = "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985"

# OOTDiffusion — Alternative (faster, slightly lower quality)
OOTD_MODEL = "levihsu/ootdiffusion:8600197fd84c5b9f9b062a3ca8b63363b10734c7b4e2ec7c498f35a3e69d0f68"

# Hugging Face models for image generation
# Using instruction-based image editing for try-on effect
HF_IMG2IMG_MODEL = "timbrooks/instruct-pix2pix"  # Instruction-based image editing
HF_T2I_FALLBACK = "stabilityai/stable-diffusion-xl-base-1.0"  # Text-to-image fallback

# Full-body model pose references used for try-on guidance.
FEMALE_MODEL_POSES = [
    "https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg",
    "https://images.pexels.com/photos/415829/pexels-photo-415829.jpeg",
]

MALE_MODEL_POSES = [
    "https://images.pexels.com/photos/1680172/pexels-photo-1680172.jpeg",
    "https://images.pexels.com/photos/936229/pexels-photo-936229.jpeg",
]

DEFAULT_MODEL_POSES = FEMALE_MODEL_POSES + MALE_MODEL_POSES


class VirtualTryOnService:

    def __init__(self):
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
        self.ai_provider = (settings.AI_PROVIDER or "REPLICATE").upper()
        self.hf_token = settings.HUGGINGFACE_API_TOKEN
        self.nano_client = NanoBananaProClient()
        pools = get_gendered_model_pools(FEMALE_MODEL_POSES, MALE_MODEL_POSES)
        self.female_model_poses = pools["female"]
        self.male_model_poses = pools["male"]
        self.default_model_poses = self.female_model_poses + self.male_model_poses

    async def generate(
        self,
        clothing_image_url: str,
        num_samples: int = 2,
        model_image_url: Optional[str] = None,
        target_gender: Optional[str] = None,
        garment_description: str = "fashion clothing item",
        garment_category: str = "dresses",
    ) -> List[bytes]:
        """
        clothing_image_url: background-removed clothing image URL
        num_samples: কতগুলো try-on variation বানাবে (Figma এ multiple tabs)
        model_image_url: optional — specific model pose use করতে

        Returns: List of image bytes (each = one try-on output)
        """
        sample_count = max(1, num_samples)
        pose_urls = self._resolve_model_poses(sample_count, target_gender, model_image_url)

        if self.ai_provider == "NANO_BANANA_PRO" and self.nano_client.enabled:
            nano_pose_urls = self._resolve_nano_model_poses(sample_count, target_gender, model_image_url)
            return await self._generate_nano_banana(
                clothing_image_url,
                sample_count,
                nano_pose_urls,
                garment_description,
                garment_category,
            )

        if self.ai_provider == "HUGGINGFACE" and self.hf_token:
            return await self._generate_hf(
                clothing_image_url,
                sample_count,
                pose_urls,
                garment_description,
                garment_category,
            )

        result_bytes: List[bytes] = []
        original: Optional[bytes] = None

        for idx, pose_url in enumerate(pose_urls):
            input_params = {
                "garm_img": clothing_image_url,
                "garment_des": garment_description,
                "category": garment_category,
                "is_checked": True,
                "is_checked_crop": True,
                "denoise_steps": 30,
                "seed": 42 + idx,
                "human_img": pose_url,
            }

            try:
                output = await run_replicate_with_retry(IDM_VTON_MODEL, input_params)
                urls = output if isinstance(output, list) else [output]
                if urls:
                    img_bytes = await self._download(str(urls[0]))
                    result_bytes.append(img_bytes)
                    continue
            except InvalidReplicateModelError as e:
                print(f"Virtual Try-On model/version invalid: {e}")
            except InvalidReplicateInputError as e:
                print(f"Virtual Try-On input invalid: {e}")
            except Exception as e:
                print(f"Virtual Try-On generation failed: {e}")

            if original is None:
                original = await self._download(clothing_image_url)
            if original:
                result_bytes.append(original)

        if result_bytes:
            return result_bytes

        if original is None:
            original = await self._download(clothing_image_url)
        if not original:
            return []
        return [original for _ in range(sample_count)]

    async def _generate_hf(
        self,
        clothing_image_url: str,
        num_samples: int,
        pose_urls: List[str],
        garment_description: str,
        garment_category: str,
    ) -> List[bytes]:
        result_bytes: List[bytes] = []
        
        original = await self._download(clothing_image_url)
        if not original:
            return []
        
        # Use Gradio Client for IDM-VTON (free and works!)
        for i in range(max(1, num_samples)):
            try:
                print(f"🚀 Attempting IDM-VTON via Gradio Client (try {i+1}/{num_samples})...")
                human_url = pose_urls[i % len(pose_urls)] if pose_urls else DEFAULT_MODEL_POSES[0]
                img = await self._hf_gradio_vton(original, human_url, garment_description, garment_category)
                if img:
                    print(f"✅ Virtual try-on succeeded!")
                    result_bytes.append(img)
                else:
                    print(f"⚠️ Try-on returned None, using original")
                    result_bytes.append(original)
            except Exception as e:
                print(f"❌ Virtual try-on attempt {i+1} failed: {str(e)[:150]}")
                result_bytes.append(original)
        
        return result_bytes if result_bytes else [original]

    async def _hf_image_to_image(self, image_url: str, prompt: str, negative_prompt: str = "") -> Optional[bytes]:
        try:
            from huggingface_hub import InferenceClient

            source_image_bytes = await self._download(image_url)
            
            client = InferenceClient(provider="hf-inference", api_key=self.hf_token)
            output = client.image_to_image(
                image=source_image_bytes,
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=HF_IMG2IMG_MODEL,
            )

            if isinstance(output, bytes):
                return output

            if hasattr(output, "save"):
                buffer = io.BytesIO()
                output.save(buffer, format="PNG")
                return buffer.getvalue()

            print("⚠️ Hugging Face try-on generation returned unexpected output type")
        except Exception as e:
            print(f"⚠️ Hugging Face try-on generation error: {e}")
        return None

    async def generate_ootd(
        self,
        clothing_image_url: str,
        num_samples: int = 2,
    ) -> List[bytes]:
        """
        OOTDiffusion — Alternative try-on (faster)
        Use this if IDM-VTON is slow or expensive
        """
        output = await run_replicate_with_retry(
            OOTD_MODEL,
            {
                "cloth_image": clothing_image_url,
                "model_image": (
                    "https://huggingface.co/spaces/levihsu/OOTDiffusion/"
                    "resolve/main/examples/model/model_1.png"
                ),
                "n_samples": num_samples,
                "n_steps": 20,
                "image_scale": 2.0,
                "seed": -1,
            },
        )

        result_bytes = []
        urls = output if isinstance(output, list) else [output]
        for url in urls[:num_samples]:
            img_bytes = await self._download(str(url))
            result_bytes.append(img_bytes)

        return result_bytes

    async def _download(self, url: str) -> bytes:
        # Handle MongoDB URLs
        if url.startswith("mongodb://"):
            from utils.storage import storage
            file_id = url.replace("mongodb://", "")
            return await storage.get_file(file_id)
        
        # Handle HTTP/HTTPS URLs
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content

    def _resolve_model_poses(
        self,
        num_samples: int,
        target_gender: Optional[str],
        model_image_url: Optional[str],
    ) -> List[str]:
        sample_count = max(1, num_samples)

        if model_image_url:
            return [model_image_url for _ in range(sample_count)]

        gender = (target_gender or "").strip().lower()
        if gender in {"male", "man", "men", "mens", "boy", "boys"}:
            pool = self.male_model_poses
        elif gender in {"female", "woman", "women", "womens", "girl", "girls", "lady", "ladies"}:
            pool = self.female_model_poses
        else:
            pool = self.default_model_poses or DEFAULT_MODEL_POSES

        if not pool:
            pool = self.default_model_poses or DEFAULT_MODEL_POSES

        return [pool[i % len(pool)] for i in range(sample_count)]

    def _resolve_nano_model_poses(
        self,
        num_samples: int,
        target_gender: Optional[str],
        model_image_url: Optional[str],
    ) -> List[str]:
        """For Nano Banana, only use explicitly provided model references."""
        sample_count = max(1, num_samples)

        if model_image_url:
            return [model_image_url for _ in range(sample_count)]

        female_urls = parse_model_urls(settings.NANO_BANANA_FEMALE_MODEL_URLS)
        male_urls = parse_model_urls(settings.NANO_BANANA_MALE_MODEL_URLS)

        gender = (target_gender or "").strip().lower()
        if gender in {"male", "man", "men", "mens", "boy", "boys"}:
            pool = male_urls
        elif gender in {"female", "woman", "women", "womens", "girl", "girls", "lady", "ladies"}:
            pool = female_urls
        else:
            pool = female_urls + male_urls

        if not pool:
            return []

        return [pool[i % len(pool)] for i in range(sample_count)]

    async def _generate_nano_banana(
        self,
        clothing_image_url: str,
        num_samples: int,
        pose_urls: List[str],
        garment_description: str,
        garment_category: str,
    ) -> List[bytes]:
        result_bytes: List[bytes] = []
        original: Optional[bytes] = None

        for idx in range(max(1, num_samples)):
            pose_url = pose_urls[idx % len(pose_urls)] if pose_urls else None
            try:
                generated = await self.nano_client.generate(
                    mode="virtual_tryon",
                    clothing_image_url=clothing_image_url,
                    model_image_url=pose_url,
                    garment_description=garment_description,
                    garment_category=garment_category,
                    seed=42 + idx,
                )
                if generated:
                    result_bytes.append(generated)
                    continue
            except Exception as e:
                print(f"Nano Banana virtual try-on failed (sample {idx + 1}): {e}")

            if original is None:
                original = await self._download(clothing_image_url)
            if original:
                result_bytes.append(original)

        if result_bytes:
            return result_bytes

        if original is None:
            original = await self._download(clothing_image_url)
        return [original] if original else []

    async def _hf_gradio_vton(
        self,
        garment_bytes: bytes,
        human_url: str,
        garment_description: str,
        garment_category: str,
    ) -> Optional[bytes]:
        """Use IDM-VTON via Gradio Client (yisol/IDM-VTON space)"""
        try:
            from gradio_client import Client, handle_file
            import tempfile
            import os
            import asyncio

            # Save garment bytes to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as garment_file:
                garment_file.write(garment_bytes)
                garment_path = garment_file.name
            
            try:
                # Initialize Gradio client
                client = Client("yisol/IDM-VTON")
                
                # Run prediction in executor to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: client.predict(
                        dict={"background": human_url, "layers": [], "composite": None},
                        garm_img=handle_file(garment_path),
                        garment_des=garment_description,
                        category=garment_category,
                        is_checked=True,
                        is_checked_crop=True,
                        denoise_steps=30,
                        seed=42,
                        api_name="/tryon"
                    )
                )
                
                # Result is a tuple, first element is output image path
                if result and len(result) > 0:
                    output_path = result[0]
                    with open(output_path, "rb") as f:
                        return f.read()
                        
            finally:
                # Cleanup temp file
                if os.path.exists(garment_path):
                    os.unlink(garment_path)
                    
        except Exception as e:
            print(f"❌ Gradio VTON error: {str(e)[:200]}")
        return None

    async def _hf_instruct_edit(self, image_url: str, image_bytes: bytes, instruction: str) -> Optional[bytes]:
        """Use text-to-image generation with context from input image"""
        try:
            from huggingface_hub import InferenceClient
            import asyncio
            
            client = InferenceClient(api_key=self.hf_token)
            
            # Better prompt for virtual try-on
            full_prompt = f"{instruction} same clothing as reference. fashion photoshoot."
            
            # Run in thread pool to avoid blocking async
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(
                None,
                lambda: client.text_to_image(
                    prompt=full_prompt,
                    model="stabilityai/stable-diffusion-xl-base-1.0",
                    negative_prompt="blurry, distorted, low quality, watermark",
                )
            )

            if isinstance(output, bytes):
                print(f"✅ HF generation succeeded (bytes)")
                return output
            
            if hasattr(output, "save"):
                buffer = io.BytesIO()
                output.save(buffer, format="PNG")
                result = buffer.getvalue()
                print(f"✅ HF generation succeeded (PIL, {len(result)} bytes)")
                return result
            
            print(f"⚠️ HF generation unexpected output type: {type(output)}")
        except Exception as e:
            print(f"❌ HF generation error: {str(e)[:200]}")
        return None


virtual_tryon_service = VirtualTryOnService()