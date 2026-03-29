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
import httpx
from typing import List, Optional
from PIL import Image, ImageDraw
from config.settings import settings
from services.features.nano_banana import NanoBananaProClient
from services.features.replicate_utils import InvalidReplicateModelError, run_replicate_with_retry


# Stable Diffusion XL for mannequin generation
SDXL_MODEL = "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc"

# Img2img for ghost mannequin effect
IMG2IMG_MODEL = "stability-ai/stable-diffusion-img2img:15a3689ee13b0d2616e98820eca31d4c3abcd36672df6afce5cb6feb1d66087d"

# Hugging Face models for image generation
HF_IMG2IMG_MODEL = "timbrooks/instruct-pix2pix"  # Instruction-based image editing
HF_T2I_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"


class MannequinService:

    def __init__(self):
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
        self.ai_provider = (settings.AI_PROVIDER or "REPLICATE").upper()
        self.hf_token = settings.HUGGINGFACE_API_TOKEN
        self.nano_client = NanoBananaProClient()

    async def generate_ghost_mannequin(
        self,
        background_removed_url: str,
        num_samples: int = 1,
    ) -> List[bytes]:
        """
        Ghost Mannequin Effect।
        Background removed clothing → 3D shaped clothing (no mannequin visible)
        
        Args:
            background_removed_url: Clean clothing image (transparent/white bg)
            num_samples: Number of variations
        
        Returns: List of mannequin image bytes
        """
        if self.ai_provider == "NANO_BANANA_PRO" and self.nano_client.enabled:
            generated = await self._generate_nano_mannequin(
                background_removed_url,
                num_samples,
                mode="ghost_mannequin",
            )
            if generated:
                return generated

        if self.ai_provider == "HUGGINGFACE" and self.hf_token:
            return await self._generate_hf_ghost(background_removed_url, num_samples)

        try:
            output = await run_replicate_with_retry(
                IMG2IMG_MODEL,
                {
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
                    "strength": 0.55,
                    "num_outputs": num_samples,
                    "guidance_scale": 8.0,
                    "scheduler": "DPMSolverMultistep",
                    "num_inference_steps": 30,
                },
            )
            return await self._download_all(output, num_samples)
        except InvalidReplicateModelError as e:
            print(f"Ghost mannequin model/version invalid: {e}")
            original = await self._download(background_removed_url)
            if not original:
                return []
            return [original for _ in range(max(1, num_samples))]
        except Exception as e:
            print(f"Ghost mannequin generation failed: {e}")
            original = await self._download(background_removed_url)
            return [original] if original else []

    async def _generate_hf_ghost(self, background_removed_url: str, num_samples: int) -> List[bytes]:
        """
        Ghost mannequin via HuggingFace.
        Note: IDM-VTON is for people/models, not suitable for ghost mannequin.
        For now, returns original image. Ghost mannequin needs specialized models.
        """
        result: List[bytes] = []
        
        print(" Ghost mannequin not yet supported via Gradio (IDM-VTON is for models only)")
        print("Returning original clothing image as fallback")
        
        original = await self._download(background_removed_url)
        if not original:
            return []
        
        # Return original image for each sample
        for i in range(max(1, num_samples)):
            result.append(original)
        
        return result

    async def generate_on_mannequin(
        self,
        background_removed_url: str,
        num_samples: int = 2,
        preserve_dress: bool = True,
    ) -> List[bytes]:
        """
        Visible Plastic Mannequin — clothing on a physical mannequin stand.
        Looks like real product photography on store mannequin.
        
        Args:
            background_removed_url: Dress image URL (background removed)
            num_samples: Number of variations
            preserve_dress: If True, uses PIL composition (fast, deterministic) and
                          keeps garment pixels unchanged.
                          If False, uses AI generation for higher variation.
        """
        if self.ai_provider == "NANO_BANANA_PRO" and self.nano_client.enabled:
            generated = await self._generate_nano_mannequin(
                background_removed_url,
                num_samples,
                mode="mannequin",
            )
            if generated:
                return generated
            print("Nano Banana mannequin returned no image; falling back to deterministic composition")

        if preserve_dress:
            # Deterministic mannequin composition keeps dress pixels unchanged.
            original = await self._download(background_removed_url)
            if not original:
                return []

            composed = self._compose_on_plastic_mannequin(original)
            if composed:
                return [composed for _ in range(max(1, num_samples))]
            return [original for _ in range(max(1, num_samples))]

        if self.ai_provider == "HUGGINGFACE" and self.hf_token:
            print("⚠️ HF fallback: Visible mannequin not yet supported via Gradio")
            print("↪️ Returning PIL mannequin composition")
            
            result: List[bytes] = []
            original = await self._download(background_removed_url)
            if not original:
                return []
            
            composed = self._compose_on_plastic_mannequin(original)
            if composed:
                return [composed for _ in range(max(1, num_samples))]
            return [original for _ in range(max(1, num_samples))]

        try:
            strength = 0.40
            
            output = await run_replicate_with_retry(
                IMG2IMG_MODEL,
                {
                    "image": background_removed_url,
                    "prompt": (
                        "dress on white plastic mannequin stand, "
                        "full body shot head to toe, "
                        "product photography white background, "
                        "professional e-commerce fashion, "
                        "perfect draping, clean sharp details, "
                        "realistic plastic mannequin, clear fabric texture"
                    ),
                    "negative_prompt": (
                        "color change, fabric distortion, size change, "
                        "altered dress shape, human model, person, face, "
                        "outdoor background, wrinkled, blurry, low quality, "
                        "modified dress, fabric texture change, watermark"
                    ),
                    "strength": strength,
                    "num_outputs": num_samples,
                    "guidance_scale": 7.5,
                    "num_inference_steps": 25,
                },
            )
            return await self._download_all(output, num_samples)
        except InvalidReplicateModelError as e:
            print(f"❌ Mannequin model invalid: {e}")
            print("↪️ Falling back to PIL composition")
            original = await self._download(background_removed_url)
            if not original:
                return []
            composed = self._compose_on_plastic_mannequin(original)
            return [composed] if composed else [original]
        except Exception as e:
            print(f"❌ Mannequin generation failed: {e}")
            print("↪️ Falling back to PIL composition")
            original = await self._download(background_removed_url)
            if not original:
                return []
            composed = self._compose_on_plastic_mannequin(original)
            return [composed] if composed else [original]

    def _compose_on_plastic_mannequin(self, dress_image_bytes: bytes) -> Optional[bytes]:
        """Compose dress over a synthetic plastic mannequin without modifying the dress pixels."""
        try:
            dress = Image.open(io.BytesIO(dress_image_bytes)).convert("RGBA")
            mannequin = self._render_mannequin_base(dress.width, dress.height)

            # Layer order: mannequin behind, dress on top.
            result = Image.alpha_composite(mannequin, dress)

            buffer = io.BytesIO()
            result.save(buffer, format="PNG")
            return buffer.getvalue()
        except Exception as e:
            print(f"Mannequin composition failed: {e}")
            return None

    def _render_mannequin_base(self, width: int, height: int) -> Image.Image:
        """Render a neutral white plastic mannequin + stand on white background."""
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        cx = width // 2
        light = (244, 244, 244, 255)
        mid = (225, 225, 225, 255)
        stand = (45, 50, 60, 255)

        # Head + neck
        head_w = int(width * 0.10)
        head_h = int(height * 0.10)
        head_y = int(height * 0.03)
        draw.ellipse((cx - head_w // 2, head_y, cx + head_w // 2, head_y + head_h), fill=light)

        neck_w = int(width * 0.05)
        neck_h = int(height * 0.05)
        neck_y = head_y + head_h - int(height * 0.005)
        draw.rounded_rectangle(
            (cx - neck_w // 2, neck_y, cx + neck_w // 2, neck_y + neck_h),
            radius=max(1, int(width * 0.008)),
            fill=mid,
        )

        # Torso
        shoulder_y = neck_y + neck_h
        hip_y = int(height * 0.68)
        shoulder_half = int(width * 0.17)
        waist_half = int(width * 0.09)
        hip_half = int(width * 0.13)
        torso_points = [
            (cx - shoulder_half, shoulder_y),
            (cx + shoulder_half, shoulder_y),
            (cx + waist_half, int(height * 0.45)),
            (cx + hip_half, hip_y),
            (cx - hip_half, hip_y),
            (cx - waist_half, int(height * 0.45)),
        ]
        draw.polygon(torso_points, fill=light)

        # Stand pole + base
        pole_top = hip_y
        pole_bottom = int(height * 0.93)
        pole_w = max(2, int(width * 0.012))
        draw.rounded_rectangle(
            (cx - pole_w // 2, pole_top, cx + pole_w // 2, pole_bottom),
            radius=max(1, pole_w // 2),
            fill=stand,
        )

        foot_y = pole_bottom
        leg_len = int(width * 0.13)
        leg_rise = int(height * 0.06)
        draw.line((cx, foot_y, cx - leg_len, foot_y + leg_rise), fill=stand, width=max(2, int(width * 0.01)))
        draw.line((cx, foot_y, cx + leg_len, foot_y + leg_rise), fill=stand, width=max(2, int(width * 0.01)))
        draw.line((cx, foot_y, cx, foot_y + leg_rise), fill=stand, width=max(2, int(width * 0.01)))

        return canvas

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

    async def _download_all(self, output, num_samples: int) -> List[bytes]:
        urls = output if isinstance(output, list) else [output]
        result: List[bytes] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for url in urls[:num_samples]:
                r = await client.get(str(url))
                r.raise_for_status()
                result.append(r.content)
        return result

    async def _generate_nano_mannequin(
        self,
        background_removed_url: str,
        num_samples: int,
        mode: str,
    ) -> List[bytes]:
        results: List[bytes] = []

        for idx in range(max(1, num_samples)):
            try:
                generated = await self.nano_client.generate(
                    mode=mode,
                    clothing_image_url=background_removed_url,
                    model_image_url=None,
                    garment_description="fashion mannequin presentation",
                    garment_category="dresses",
                    seed=300 + idx,
                )
                if generated:
                    results.append(generated)
                    continue
            except Exception as e:
                print(f"Nano Banana mannequin generation failed (sample {idx + 1}): {e}")

        if results:
            return results
        return []

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


mannequin_service = MannequinService()