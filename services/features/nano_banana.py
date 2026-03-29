"""
Nano Banana Pro Client
======================
Thin async wrapper for Nano Banana Pro image generation endpoints.

The API shape can vary by deployment, so this client is intentionally
lenient while parsing responses (URL, list, nested data, or base64).
"""

from __future__ import annotations

import base64
import imghdr
from typing import Dict, List, Optional

import httpx

from config.settings import settings


class NanoBananaProClient:
    """Small client for Nano Banana Pro API integration."""

    def __init__(self) -> None:
        self.gemini_api_key = (settings.GEMINI_API_KEY or "").strip()
        self.api_key = (settings.NANO_BANANA_PRO_API_KEY or "").strip()
        self.base_url = (settings.NANO_BANANA_PRO_BASE_URL or "").strip().rstrip("/")
        self.endpoint_path = (settings.NANO_BANANA_PRO_ENDPOINT_PATH or "/generate").strip()
        if not self.endpoint_path.startswith("/"):
            self.endpoint_path = f"/{self.endpoint_path}"
        self.timeout_seconds = max(15, int(settings.NANO_BANANA_PRO_TIMEOUT_SECONDS or 120))

    @property
    def enabled(self) -> bool:
        has_custom = bool(self.api_key and self.base_url)
        has_gemini = bool(self.gemini_api_key)
        return has_custom or has_gemini

    async def generate(
        self,
        *,
        mode: str,
        clothing_image_url: str,
        model_image_url: Optional[str],
        garment_description: str,
        garment_category: str,
        seed: Optional[int] = None,
        extra: Optional[Dict] = None,
    ) -> Optional[bytes]:
        """Generate one image and return image bytes if successful."""
        if not self.enabled:
            return None

        # Preferred path: direct Gemini/Nano Banana model call using GEMINI_API_KEY.
        if self.gemini_api_key:
            generated = await self._generate_via_gemini(
                mode=mode,
                clothing_image_url=clothing_image_url,
                model_image_url=model_image_url,
                garment_description=garment_description,
                garment_category=garment_category,
            )
            if generated:
                return generated

        # Fallback path: custom Nano Banana endpoint (if configured).
        if not (self.api_key and self.base_url):
            return None

        payload: Dict = {
            "model": settings.NANO_BANANA_PRO_MODEL,
            "mode": mode,
            "clothing_image_url": clothing_image_url,
            "garment_description": garment_description,
            "garment_category": garment_category,
            "seed": seed,
        }
        if model_image_url:
            payload["model_image_url"] = model_image_url
        if extra:
            payload.update(extra)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json,image/*",
        }

        url = f"{self.base_url}{self.endpoint_path}"

        async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()

            content_type = (r.headers.get("content-type") or "").lower()
            if content_type.startswith("image/"):
                return r.content

            data = r.json() if r.content else {}
            image_url = self._extract_image_url(data)
            if image_url:
                return await self._download(image_url)

            image_b64 = self._extract_image_base64(data)
            if image_b64:
                try:
                    return base64.b64decode(image_b64)
                except Exception:
                    return None

        return None

    async def _generate_via_gemini(
        self,
        *,
        mode: str,
        clothing_image_url: str,
        model_image_url: Optional[str],
        garment_description: str,
        garment_category: str,
    ) -> Optional[bytes]:
        """Call Gemini model directly and extract generated image bytes."""
        model_name = (settings.NANO_BANANA_PRO_MODEL or "nano-banana-pro-preview").strip()
        if model_name == "nano-banana-pro":
            model_name = "nano-banana-pro-preview"

        clothing_bytes = await self._download(clothing_image_url)
        if not clothing_bytes:
            return None

        model_bytes: Optional[bytes] = None
        if model_image_url:
            try:
                model_bytes = await self._download(model_image_url)
            except Exception:
                model_bytes = None

        prompt = self._build_prompt(mode, garment_description, garment_category)

        parts: List[Dict] = [{"text": prompt}]
        parts.append({
            "inlineData": {
                "mimeType": self._detect_mime_type(clothing_bytes),
                "data": base64.b64encode(clothing_bytes).decode("utf-8"),
            }
        })
        if model_bytes:
            parts.append({
                "inlineData": {
                    "mimeType": self._detect_mime_type(model_bytes),
                    "data": base64.b64encode(model_bytes).decode("utf-8"),
                }
            })

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
                "candidateCount": 1,
                "temperature": 0.2,
            },
        }

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={self.gemini_api_key}"
        )

        async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
            r = await client.post(url, json=body)
            r.raise_for_status()
            data = r.json() if r.content else {}

        image_b64 = self._extract_gemini_inline_image(data)
        if image_b64:
            try:
                return base64.b64decode(image_b64)
            except Exception:
                return None

        # Sometimes providers proxy image URLs even for Gemini path.
        image_url = self._extract_image_url(data)
        if image_url:
            return await self._download(image_url)

        return None

    def _extract_gemini_inline_image(self, data: Dict) -> Optional[str]:
        if not isinstance(data, dict):
            return None

        candidates = data.get("candidates")
        if not isinstance(candidates, list):
            return None

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline = part.get("inlineData")
                if isinstance(inline, dict):
                    img_data = inline.get("data")
                    if isinstance(img_data, str) and img_data:
                        return img_data

        return None

    def _build_prompt(
        self,
        mode: str,
        garment_description: str,
        garment_category: str,
    ) -> str:
        category_text = garment_category or "dresses"
        garment_text = garment_description or "fashion clothing item"

        if mode == "virtual_tryon":
            return (
                "Create ONE high-quality realistic virtual try-on image for e-commerce. "
                "The FIRST image is the garment reference and MUST be preserved exactly. "
                "If a SECOND reference person image exists, use it for body/pose identity. "
                "If no person reference exists, create a natural realistic model automatically. "
                "MANDATORY framing: full-body head-to-toe, feet visible, centered subject, not cropped. "
                "MANDATORY garment fidelity: do NOT change garment color, print, pattern, texture, fabric details, "
                "silhouette, sleeve length, neckline, or design elements. "
                "Do not recolor, restyle, invent logos, or alter cloth quality. "
                "Use neutral clean studio/e-commerce background and realistic lighting. "
                f"Garment description: {garment_text}. Category: {category_text}."
            )
        if mode == "model":
            return (
                "Generate a realistic fashion model photo wearing the provided garment reference. "
                "Use the second image as model identity/pose guidance when available. "
                f"Garment: {garment_text}. Category: {category_text}. "
                "Keep clothing details faithful and produce one high-quality full-body output."
            )
        if mode == "ghost_mannequin":
            return (
                "Create a ghost mannequin e-commerce image from the garment reference. "
                "Do not show any human model. Preserve fabric details and shape. "
                "White clean studio background."
            )
        return (
            "Create ONE realistic plastic mannequin product photo using the garment reference image. "
            "Show a white/neutral full-body mannequin stand from head to toe, centered, feet/base visible, no crop. "
            "Do NOT generate a human person or skin. Mannequin must look like retail display plastic mannequin. "
            "MANDATORY garment fidelity: keep the exact original dress color, pattern, print, texture, cloth quality, "
            "stitching details, silhouette, and design unchanged. "
            "Do not recolor, do not change fabric quality, do not alter fit style. "
            "Use clean e-commerce studio background and lighting."
        )

    def _detect_mime_type(self, image_bytes: bytes) -> str:
        guessed = imghdr.what(None, image_bytes)
        if guessed == "png":
            return "image/png"
        if guessed in {"jpeg", "jpg"}:
            return "image/jpeg"
        if guessed == "webp":
            return "image/webp"
        return "image/png"

    async def _download(self, url: str) -> bytes:
        # Support local MongoDB storage URLs in this project.
        if url.startswith("mongodb://"):
            from utils.storage import storage

            file_id = url.replace("mongodb://", "")
            return await storage.get_file(file_id)

        async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content

    def _extract_image_url(self, data: Dict) -> Optional[str]:
        if not isinstance(data, dict):
            return None

        # Common direct keys
        for key in ["image_url", "url", "output_url", "result_url"]:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        # Common list keys
        for key in ["images", "outputs", "result", "data"]:
            value = data.get(key)
            found = self._first_url_from_collection(value)
            if found:
                return found

        return None

    def _first_url_from_collection(self, value) -> Optional[str]:
        if isinstance(value, str) and value.strip():
            return value.strip()

        if isinstance(value, dict):
            for key in ["url", "image_url", "output_url"]:
                v = value.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

        if isinstance(value, list):
            for item in value:
                found = self._first_url_from_collection(item)
                if found:
                    return found

        return None

    def _extract_image_base64(self, data: Dict) -> Optional[str]:
        if not isinstance(data, dict):
            return None

        for key in ["image_base64", "b64", "image"]:
            value = data.get(key)
            if isinstance(value, str) and len(value) > 100:
                return value

        return None


def parse_model_urls(raw_value: str) -> List[str]:
    """Parse comma/newline separated URL strings into a clean list."""
    if not raw_value:
        return []

    parts = raw_value.replace("\n", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def get_gendered_model_pools(default_female: List[str], default_male: List[str]) -> Dict[str, List[str]]:
    """Return gender model pools, preferring env-configured URLs when provided."""
    female = parse_model_urls(settings.NANO_BANANA_FEMALE_MODEL_URLS)
    male = parse_model_urls(settings.NANO_BANANA_MALE_MODEL_URLS)

    return {
        "female": female or list(default_female),
        "male": male or list(default_male),
    }
