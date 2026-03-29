"""
Product Listing Generator — Gemini
====================================
Image + detected features → Complete product listing।
Figma → Product Listing Preview section এর সব fields generate করে।
"""

import google.generativeai as genai
import json
import base64
from typing import Dict, List, Optional
from config.settings import settings


class ProductListingService:

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def generate(self, image_bytes: bytes) -> Dict:
        """
        Garment image → Complete product listing data।
        
        Returns dict matching Figma's Product Listing Preview:
          - product_title, description
          - product_details (category, brand, sleeve_length, dress_type, age_group, gender)
          - variant_data (sizes, colors, condition, feature)
          - tags
          - seo_tags
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """You are an expert fashion e-commerce product listing specialist.

Analyze this garment image and generate a complete product listing.

Return ONLY a JSON object with these exact fields:
{
    "product_title": "Women's Floral Summer Dress",
    "description": "A lightweight, breathable floral dress designed for everyday comfort...(150 words)",
    "media": "Picture",
    "product_details": {
        "category": "Women > Dresses",
        "brand": "Local Designer",
        "sleeve_length": "Short",
        "dress_type": "A-line",
        "age_group": "18-35",
        "gender": "Female"
    },
    "variant_data": {
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Blue", "Pink"],
        "condition": "New",
        "feature": "Floral print"
    },
    "tags": ["vintage", "cotton", "casual", "summer", "unisex"],
    "seo_tags": ["summer dress", "floral dress", "women clothing", "casual wear"],
    "fabric": "100% Cotton",
    "product_code": "DR-1023",
    "care_instructions": "Machine wash cold. Tumble dry low. Do not bleach.",
    "key_features": ["Breathable fabric", "Relaxed fit", "Versatile styling"]
}

Rules:
- product_title: max 60 chars, catchy and specific
- description: 50 words, professional fashion copywriting
- category: use "Parent > Child" format
- tags: 5-7 relevant fashion tags
- Output ONLY valid JSON, no markdown"""

        response = await self.model.generate_content_async([
            {"mime_type": "image/jpeg", "data": image_b64},
            prompt,
        ])

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return self._fallback_listing()

    def _fallback_listing(self) -> Dict:
        return {
            "product_title": "Fashion Clothing Item",
            "description": "A stylish clothing item perfect for everyday wear. "
                           "Crafted with quality materials for comfort and durability. "
                           "Versatile design suitable for various occasions.",
            "media": "Picture",
            "product_details": {
                "category": "Clothing",
                "brand": "Local Designer",
                "sleeve_length": "Regular",
                "dress_type": "Regular",
                "age_group": "18-35",
                "gender": "Unisex",
            },
            "variant_data": {
                "sizes": ["S", "M", "L", "XL"],
                "colors": ["Multicolor"],
                "condition": "New",
                "feature": "Standard",
            },
            "tags": ["fashion", "clothing", "casual", "style"],
            "seo_tags": ["fashion clothing", "casual wear", "trendy"],
            "fabric": "Mixed",
            "product_code": f"PR-{__import__('uuid').uuid4().hex[:6].upper()}",
            "care_instructions": "Follow care label instructions.",
            "key_features": ["Quality fabric", "Comfortable fit"],
        }


product_listing_service = ProductListingService()