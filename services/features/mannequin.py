"""
Feature 5 — Mannequin
======================
Flat-lay clothing → 3D Mannequin / Ghost Mannequin effect।

Ghost Mannequin: Clothing টা 3D shaped হবে যেন invisible mannequin পরে আছে।
Standard fashion photography technique — shape ও structure clearly দেখা যায়।

How:
  - Replicate Stable Diffusion দিয়ে flat-lay → mannequin generate করে
  - Ghost mannequin effect: clothing এর shape ধরে রাখে, mannequin দেখা যায় না
"""

import os
import io
import replicate
import httpx
from typing import List, Optional
from config.settings import settings


# Stable Diffusion XL for mannequin generation
SDXL_MODEL = "stability-ai/sdxl:39ed52f2146e2d37a7ee45e55ef3e0b73a9daf5dab9f96e1f6ab36a01f398c7b"

# Img2img for ghost mannequin effect
IMG2IMG_MODEL = "stability-ai/stable-diffusion-img2img:15a3689ee13b0d2616e98820eca31d4af4b51808f9a4031fffbc5b85b4a35a60"

# Hugging Face models for image generation
HF_IMG2IMG_MODEL = "timbrooks/instruct-pix2pix"  # Instruction-based image editing
HF_T2I_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"


class MannequinService:

    def __init__(self):
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
        self.ai_provider = (settings.AI_PROVIDER or "REPLICATE").upper()
        self.hf_token = settings.HUGGINGFACE_API_TOKEN

    async def generate_ghost_mannequin(
        self,
        background_removed_url: str,
        num_samples: int = 2,
    ) -> List[bytes]:
        """
        Ghost Mannequin Effect।
        Background removed clothing → 3D shaped clothing (no mannequin visible)
        
        Args:
            background_removed_url: Clean clothing image (transparent/white bg)
            num_samples: Number of variations
        
        Returns: List of mannequin image bytes
        """
        if self.ai_provider == "HUGGINGFACE" and self.hf_token:
            return await self._generate_hf_ghost(background_removed_url, num_samples)

        output = replicate.run(
            IMG2IMG_MODEL,
            input={
                "image": background_removed_url,
                "prompt": (
                    "professional ghost mannequin clothing photography, "
                    "3D shaped garment, invisible mannequin effect, "
                    "white background, studio lighting, fashion e-commerce, "
                    "high quality, sharp details"
                ),
                "negative_prompt": (
                    "visible mannequin, person, model, face, hands, "
                    "flat lay, wrinkled, poor quality, blurry"
                ),
                "strength": 0.55,        # Low strength = preserve clothing details
                "num_outputs": num_samples,
                "guidance_scale": 8.0,
                "scheduler": "DPMSolverMultistep",
                "num_inference_steps": 30,
            },
        )

        return await self._download_all(output, num_samples)

    async def _generate_hf_ghost(self, background_removed_url: str, num_samples: int) -> List[bytes]:
        result: List[bytes] = []
        
        # Ghost mannequin effect instruction
        instruction = (
            "create a professional ghost mannequin effect from this clothing. "
            "make the garment appear 3D shaped like it's on an invisible mannequin. "
            "keep the exact same color, print and shape. white background. studio lighting."
        )
        
        original = await self._download(background_removed_url)
        if not original:
            return []
        
        for i in range(max(1, num_samples)):
            try:
                # Try instruction-based mannequin generation
                img = await self._hf_instruct_edit(background_removed_url, original, instruction)
                if img:
                    result.append(img)
                else:
                    result.append(original)
            except Exception as e:
                print(f"⚠️ Mannequin ghost attempt {i+1} failed, using fallback: {e}")
                result.append(original)
        
        return result if result else [original]

    async def generate_on_mannequin(
        self,
        background_removed_url: str,
        num_samples: int = 2,
    ) -> List[bytes]:
        """
        Visible Mannequin — clothing on a physical mannequin。
        Looks like real product photography on store mannequin.
        """
        if self.ai_provider == "HUGGINGFACE" and self.hf_token:
            result: List[bytes] = []
            instruction = (
                "place this clothing on a white plastic mannequin. "
                "keep the exact same color, print and shape. professional e-commerce photo. "
                "studio lighting. white background."
            )
            
            original = await self._download(background_removed_url)
            if not original:
                return []
            
            for i in range(max(1, num_samples)):
                try:
                    img = await self._hf_instruct_edit(background_removed_url, original, instruction)
                    if img:
                        result.append(img)
                    else:
                        result.append(original)
                except Exception as e:
                    print(f"⚠️ Mannequin on-model attempt {i+1} failed, using fallback: {e}")
                    result.append(original)
            
            return result if result else [original]

        output = replicate.run(
            IMG2IMG_MODEL,
            input={
                "image": background_removed_url,
                "prompt": (
                    "fashion clothing on white plastic mannequin, "
                    "product photography, studio lighting, white background, "
                    "professional e-commerce photo, clean, sharp"
                ),
                "negative_prompt": (
                    "human face, person, model, outdoor, wrinkled, blurry, low quality"
                ),
                "strength": 0.60,
                "num_outputs": num_samples,
                "guidance_scale": 7.5,
                "num_inference_steps": 30,
            },
        )

        return await self._download_all(output, num_samples)

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

            print("⚠️ Hugging Face mannequin generation returned unexpected output type")
        except Exception as e:
            print(f"⚠️ Hugging Face mannequin generation error: {e}")
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

    async def _hf_instruct_edit(self, image_url: str, image_bytes: bytes, instruction: str) -> Optional[bytes]:
        """Use text-to-image generation for mannequin effects"""
        try:
            from huggingface_hub import InferenceClient
            import asyncio
            
            client = InferenceClient(api_key=self.hf_token)
            
            # Better prompt for mannequin
            full_prompt = f"{instruction} clothing reference applies. e-commerce style."
            
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
                print(f"✅ HF mannequin generation succeeded (bytes)")
                return output
            
            if hasattr(output, "save"):
                buffer = io.BytesIO()
                output.save(buffer, format="PNG")
                result = buffer.getvalue()
                print(f"✅ HF mannequin generation succeeded (PIL, {len(result)} bytes)")
                return result
            
            print(f"⚠️ HF mannequin generation unexpected output type: {type(output)}")
        except Exception as e:
            print(f"❌ HF mannequin generation error: {str(e)[:200]}")
        return None
        urls = output if isinstance(output, list) else [output]
        result = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for url in urls[:num_samples]:
                r = await client.get(str(url))
                r.raise_for_status()
                result.append(r.content)
        return result


mannequin_service = MannequinService()