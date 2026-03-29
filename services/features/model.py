"""
Feature 6 — Model
==================
Clothing → Realistic human model photos।

Virtual Try-On এর চেয়ে আলাদা:
  - এখানে multiple diverse models generate হয়
  - Different body types, poses, backgrounds
  - Professional fashion photography quality
  - Figma তে "On-Model Visualization" label — Image 6 দেখো

Models used:
  - IDM-VTON for highest quality
  - SDXL ControlNet for pose variation
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


IDM_VTON_MODEL = "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985"
SDXL_MODEL = "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc"
# Hugging Face models for image generation
HF_IMG2IMG_MODEL = "timbrooks/instruct-pix2pix"  # Instruction-based image editing
HF_T2I_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"  # Text-to-image

# Default model poses (diverse body types)
FEMALE_MODEL_POSES = [
    # Public full-body sample pose URLs.
    "https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg",
    "https://images.pexels.com/photos/415829/pexels-photo-415829.jpeg",
]

MALE_MODEL_POSES = [
    "https://images.pexels.com/photos/1680172/pexels-photo-1680172.jpeg",
    "https://images.pexels.com/photos/936229/pexels-photo-936229.jpeg",
]

DEFAULT_MODEL_POSES = FEMALE_MODEL_POSES + MALE_MODEL_POSES


class ModelService:

    def __init__(self):
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
        self.ai_provider = (settings.AI_PROVIDER or "REPLICATE").upper()
        self.hf_token = settings.HUGGINGFACE_API_TOKEN
        self.nano_client = NanoBananaProClient()
        pools = get_gendered_model_pools(FEMALE_MODEL_POSES, MALE_MODEL_POSES)
        self.female_model_poses = pools["female"]
        self.male_model_poses = pools["male"]
        self.default_model_poses = self.female_model_poses + self.male_model_poses

    async def generate_on_model(
        self,
        clothing_image_url: str,
        garment_description: str = "fashion clothing",
        num_samples: int = 1,
        custom_model_url: Optional[str] = None,
        target_gender: Optional[str] = None,
        garment_category: str = "dresses",
    ) -> List[bytes]:
        """
        Clothing image → Realistic model wearing the clothing。
        
        Args:
            clothing_image_url : Background-removed clothing URL (best results)
            garment_description: Short clothing description for better AI understanding
            num_samples        : কতগুলো model variation (= image tabs in Figma)
            custom_model_url   : Specific model pose image (optional)
        
        Returns: List of model image bytes
        """
        sample_count = max(1, num_samples)
        poses = self._resolve_model_poses(sample_count, target_gender, custom_model_url)

        if self.ai_provider == "NANO_BANANA_PRO" and self.nano_client.enabled:
            nano_poses = self._resolve_nano_model_poses(sample_count, target_gender, custom_model_url)
            return await self._generate_nano_banana_on_model(
                clothing_image_url,
                garment_description,
                garment_category,
                sample_count,
                nano_poses,
            )

        if self.ai_provider == "HUGGINGFACE" and self.hf_token:
            return await self._generate_hf_on_model(
                clothing_image_url,
                garment_description,
                sample_count,
                poses,
            )

        results = []

        for pose_url in poses:
            try:
                output = await run_replicate_with_retry(
                    IDM_VTON_MODEL,
                    {
                        "human_img": pose_url,
                        "garm_img": clothing_image_url,
                        "garment_des": garment_description,
                        "category": garment_category,
                        "is_checked": True,
                        "is_checked_crop": True,
                        "denoise_steps": 30,
                        "seed": -1,     # Random seed for variation
                    },
                )

                img_bytes = await self._download(str(output))
                results.append(img_bytes)

            except InvalidReplicateModelError as e:
                print(f"Model generation model/version invalid: {e}")
                print("Replicate model/version invalid; skipping model output")
                return results
            except InvalidReplicateInputError as e:
                print(f"Model generation input invalid: {e}, trying fallback...")
                fallback = await self._sdxl_fallback(clothing_image_url, garment_description)
                if fallback:
                    results.append(fallback)
            except Exception as e:
                print(f"Model generation pose failed: {e}, trying fallback...")
                # Fallback: SDXL text-to-image
                fallback = await self._sdxl_fallback(clothing_image_url, garment_description)
                if fallback:
                    results.append(fallback)

        return results

    async def _generate_hf_on_model(
        self,
        clothing_image_url: str,
        garment_description: str,
        num_samples: int,
        pose_urls: List[str],
    ) -> List[bytes]:
        results: List[bytes] = []
        
        original = await self._download(clothing_image_url)
        if not original:
            return []
        
        # Use Gradio Client for IDM-VTON model generation
        for i in range(max(1, num_samples)):
            try:
                print(f"Attempting model generation via Gradio Client (try {i+1}/{num_samples})...")
                human_url = pose_urls[i % len(pose_urls)] if pose_urls else DEFAULT_MODEL_POSES[0]
                img = await self._hf_gradio_vton(original, garment_description, human_url)
                if img:
                    print(f"Model generation succeeded!")
                    results.append(img)
                else:
                    print(f"Model generation returned None, using original")
                    results.append(original)
            except Exception as e:
                print(f"Model generation attempt {i+1} failed: {str(e)[:150]}")
                results.append(original)
        
        return results if results else [original]

    async def _sdxl_fallback(
        self,
        clothing_url: str,
        garment_description: str,
    ) -> Optional[bytes]:
        """
        IDM-VTON fail হলে SDXL img2img দিয়ে fallback।
        """
        try:
            output = await run_replicate_with_retry(
                "stability-ai/stable-diffusion-img2img:15a3689ee13b0d2616e98820eca31d4c3abcd36672df6afce5cb6feb1d66087d",
                {
                    "image": clothing_url,
                    "prompt": (
                        f"beautiful fashion model wearing {garment_description}, "
                        "professional fashion photography, studio lighting, "
                        "white background, full body shot, high quality, 8k"
                    ),
                    "negative_prompt": "flat lay, mannequin, plastic, face distortion, low quality, blurry",
                    "strength": 0.70,
                    "num_outputs": 1,
                    "guidance_scale": 8.0,
                    "num_inference_steps": 30,
                },
            )
            urls = output if isinstance(output, list) else [output]
            if urls:
                return await self._download(str(urls[0]))
        except InvalidReplicateModelError as e:
            print(f"SDXL fallback model/version invalid: {e}")
        except Exception as e:
            print(f"SDXL fallback also failed: {e}")
        return None

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

            print("Hugging Face model generation returned unexpected output type")
        except Exception as e:
            print(f"Hugging Face model generation error: {e}")
        return None

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
        custom_model_url: Optional[str],
    ) -> List[str]:
        sample_count = max(1, num_samples)

        if custom_model_url:
            return [custom_model_url for _ in range(sample_count)]

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
        custom_model_url: Optional[str],
    ) -> List[str]:
        """For Nano Banana, only use explicitly provided model references."""
        sample_count = max(1, num_samples)

        if custom_model_url:
            return [custom_model_url for _ in range(sample_count)]

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

    async def _generate_nano_banana_on_model(
        self,
        clothing_image_url: str,
        garment_description: str,
        garment_category: str,
        num_samples: int,
        pose_urls: List[str],
    ) -> List[bytes]:
        results: List[bytes] = []
        original: Optional[bytes] = None

        for idx in range(max(1, num_samples)):
            pose_url = pose_urls[idx % len(pose_urls)] if pose_urls else None
            try:
                generated = await self.nano_client.generate(
                    mode="model",
                    clothing_image_url=clothing_image_url,
                    model_image_url=pose_url,
                    garment_description=garment_description,
                    garment_category=garment_category,
                    seed=101 + idx,
                )
                if generated:
                    results.append(generated)
                    continue
            except Exception as e:
                print(f"Nano Banana model generation failed (sample {idx + 1}): {e}")

            if original is None:
                original = await self._download(clothing_image_url)
            if original:
                results.append(original)

        if results:
            return results

        if original is None:
            original = await self._download(clothing_image_url)
        return [original] if original else []

    async def _hf_gradio_vton(
        self,
        garment_bytes: bytes,
        garment_description: str,
        human_url: str,
    ) -> Optional[bytes]:
        """Use IDM-VTON via Gradio Client for model generation"""
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
                        category="dresses",
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
            print(f"Gradio Model VTON error: {str(e)[:200]}")
        return None

    async def _hf_instruct_edit(self, image_url: str, image_bytes: bytes, instruction: str) -> Optional[bytes]:
        """Use text-to-image generation with context from input image"""
        try:
            from huggingface_hub import InferenceClient
            import asyncio
            
            client = InferenceClient(api_key=self.hf_token)
            
            # Better prompt for model generation
            full_prompt = f"{instruction} same clothing as reference. professional fashion photoshoot."
            
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
                print(f"HF model generation succeeded (bytes)")
                return output
            
            if hasattr(output, "save"):
                buffer = io.BytesIO()
                output.save(buffer, format="PNG")
                result = buffer.getvalue()
                print(f"HF model generation succeeded (PIL, {len(result)} bytes)")
                return result
            
            print(f"HF model generation unexpected output type: {type(output)}")
        except Exception as e:
            print(f"HF model generation error: {str(e)[:200]}")
        return None


model_service = ModelService()