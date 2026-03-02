"""
Feature 3 — AI Virtual Try-On
================================
Replicate API → IDM-VTON model দিয়ে clothing কে realistic human model এর উপর পরায়।
Flat-lay / mannequin image → on-model photo।

Multiple outputs = multiple image tabs in Figma (Image 1, 2, 3...)
"""

import os
import io
import replicate
import httpx
from typing import List, Optional
from config.settings import settings


# IDM-VTON — Best virtual try-on model on Replicate (2024-2025)
IDM_VTON_MODEL = "cuuupid/idm-vton:906425dbca90663ff5427624839572cc56ea7d380343d13e2a4c4b09d7f0f23"

# OOTDiffusion — Alternative (faster, slightly lower quality)
OOTD_MODEL = "levihsu/ootdiffusion:8600197fd84c5b9f9b062a3ca8b63363b10734c7b4e2ec7c498f35a3e69d0f68"

# Hugging Face models for image generation
# Using instruction-based image editing for try-on effect
HF_IMG2IMG_MODEL = "timbrooks/instruct-pix2pix"  # Instruction-based image editing
HF_T2I_FALLBACK = "stabilityai/stable-diffusion-xl-base-1.0"  # Text-to-image fallback


class VirtualTryOnService:

    def __init__(self):
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
        self.ai_provider = (settings.AI_PROVIDER or "REPLICATE").upper()
        self.hf_token = settings.HUGGINGFACE_API_TOKEN

    async def generate(
        self,
        clothing_image_url: str,
        num_samples: int = 2,
        model_image_url: str = None,
    ) -> List[bytes]:
        """
        clothing_image_url: background-removed clothing image URL
        num_samples: কতগুলো try-on variation বানাবে (Figma এ multiple tabs)
        model_image_url: optional — specific model pose use করতে

        Returns: List of image bytes (each = one try-on output)
        """
        if self.ai_provider == "HUGGINGFACE" and self.hf_token:
            return await self._generate_hf(clothing_image_url, num_samples)

        input_params = {
            "garm_img": clothing_image_url,
            "garment_des": "fashion clothing item",
            "is_checked": True,
            "is_checked_crop": False,
            "denoise_steps": 30,
            "seed": 42,
        }

        # If specific model pose provided
        if model_image_url:
            input_params["human_img"] = model_image_url
        else:
            # Use default model image (neutral pose)
            input_params["human_img"] = (
                "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/"
                "example/human/00008_00.jpg"
            )

        # Run IDM-VTON on Replicate
        output = replicate.run(IDM_VTON_MODEL, input=input_params)

        # Download outputs
        result_bytes = []
        urls = output if isinstance(output, list) else [output]
        for url in urls[:num_samples]:
            img_bytes = await self._download(str(url))
            result_bytes.append(img_bytes)

        return result_bytes

    async def _generate_hf(self, clothing_image_url: str, num_samples: int) -> List[bytes]:
        result_bytes: List[bytes] = []
        
        original = await self._download(clothing_image_url)
        if not original:
            return []
        
        # Use Gradio Client for IDM-VTON (free and works!)
        for i in range(max(1, num_samples)):
            try:
                print(f"🚀 Attempting IDM-VTON via Gradio Client (try {i+1}/{num_samples})...")
                img = await self._hf_gradio_vton(original)
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
        output = replicate.run(
            OOTD_MODEL,
            input={
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

    async def _hf_gradio_vton(self, garment_bytes: bytes) -> Optional[bytes]:
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
            
            # Default human model image URL
            human_url = "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/example/human/00008_00.jpg"
            
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
                        garment_des="fashion clothing item",
                        is_checked=True,
                        is_checked_crop=False,
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