"""
Feature 1 — Physical Dimensions
================================
Flat-lay garment image থেকে real-world measurements extract করে।

How:
  - Gemini Vision দিয়ে image analyze করে pixel measurements নেয়
  - Reference scale/ruler visible থাকলে pixel-to-cm convert করে
  - যদি ruler না থাকে, garment type অনুযায়ী AI estimate করে
  - Output: chest, waist, back length, sleeve, under bust, dress length (inches + cm)
"""

import google.generativeai as genai
import json
import base64
from typing import Optional
from config.settings import settings
from models.product import PhysicalDimensions


class PhysicalDimensionsService:

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def extract(self, image_bytes: bytes) -> PhysicalDimensions:
        """
        Image থেকে physical measurements বের করে।
        Returns PhysicalDimensions with inches & cm values.
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """You are an expert fashion measurement analyst.

Analyze this flat-lay garment image carefully and extract all physical measurements.

If there is a visible ruler, measuring tape, or scale reference in the image, use it to calculate accurate real-world measurements.
If no ruler is visible, estimate based on standard garment proportions and the garment type.

Return ONLY a JSON object with these exact fields (values in inches as float, null if not applicable):
{
    "chest_width_in": <float or null>,
    "back_length_in": <float or null>,
    "waist_width_in": <float or null>,
    "sleeve_length_in": <float or null>,
    "under_bust_in": <float or null>,
    "dress_length_in": <float or null>,
    "available_sizes": ["S", "M", "L", "XL"],
    "size_guide": "<brief size recommendation string>",
    "has_ruler_reference": <true or false>,
    "confidence": "<high|medium|low>"
}

Rules:
- All measurements in INCHES as decimal (e.g. 18.0, 7.5)
- available_sizes: determine based on measurements
- size_guide: e.g. "Fits sizes 8-12 (US). Relaxed fit."
- Output ONLY valid JSON, no markdown, no extra text"""

        response = await self.model.generate_content_async([
            {"mime_type": "image/jpeg", "data": image_b64},
            prompt,
        ])

        raw = response.text.strip()
        # Clean markdown if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: return estimated defaults
            data = {
                "chest_width_in": 18.0,
                "back_length_in": 38.0,
                "waist_width_in": 14.0,
                "sleeve_length_in": 7.0,
                "under_bust_in": 13.0,
                "dress_length_in": 40.0,
                "available_sizes": ["S", "M", "L", "XL"],
                "size_guide": "Standard sizing. Please refer to size chart.",
            }

        return PhysicalDimensions(
            chest_width_in=data.get("chest_width_in"),
            back_length_in=data.get("back_length_in"),
            waist_width_in=data.get("waist_width_in"),
            sleeve_length_in=data.get("sleeve_length_in"),
            under_bust_in=data.get("under_bust_in"),
            dress_length_in=data.get("dress_length_in"),
            available_sizes=data.get("available_sizes", ["S", "M", "L", "XL"]),
            size_guide=data.get("size_guide"),
            has_ruler_reference=data.get("has_ruler_reference"),
            confidence=data.get("confidence"),
        )


physical_dimensions_service = PhysicalDimensionsService()