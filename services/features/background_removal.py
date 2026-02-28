"""
Feature 2 — Background Removal
================================
Remove.bg API দিয়ে garment image থেকে background সরায়।
Output: Clean PNG with transparent/white background।
"""

import httpx
from config.settings import settings

REMOVEBG_URL = "https://api.remove.bg/v1.0/removebg"


class BackgroundRemovalService:

    async def remove(self, image_bytes: bytes) -> bytes:
        """
        Input : Raw garment image bytes (JPG/PNG)
        Output: Background-removed PNG bytes (transparent)
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                REMOVEBG_URL,
                headers={"X-Api-Key": settings.REMOVEBG_API_KEY},
                files={"image_file": ("image.jpg", image_bytes, "image/jpeg")},
                data={
                    "size": "auto",
                    "format": "png",
                    "type": "product",         # optimized for clothing/product images
                    "crop": "false",
                    "add_shadow": "false",
                },
            )

        if response.status_code == 200:
            return response.content
        else:
            raise Exception(
                f"Remove.bg failed [{response.status_code}]: {response.text}"
            )

    async def remove_with_white_bg(self, image_bytes: bytes) -> bytes:
        """
        Background remove করে white background add করে।
        E-commerce product photo standard।
        """
        from PIL import Image
        import io

        # Remove background (transparent PNG)
        transparent_bytes = await self.remove(image_bytes)

        # Composite onto white background
        fg = Image.open(io.BytesIO(transparent_bytes)).convert("RGBA")
        bg = Image.new("RGBA", fg.size, (255, 255, 255, 255))
        bg.paste(fg, mask=fg.split()[3])
        final = bg.convert("RGB")

        buf = io.BytesIO()
        final.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


background_removal_service = BackgroundRemovalService()