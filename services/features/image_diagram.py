"""
Feature 4 — Image Diagram (Measurement Diagram)
=================================================
Clothing image এর উপর measurement lines, arrows, labels overlay করে।
Figma তে "Measurement Diagram" — garment এ annotation আঁকা দেখা যাচ্ছে।

How:
  - Gemini Vision দিয়ে key measurement points detect করে (coordinates)
  - Pillow/PIL দিয়ে arrows + dimension labels draw করে
  - Output: Annotated clothing image with measurement overlay
"""

import io
import json
import base64
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
from config.settings import settings
from models.product import PhysicalDimensions


class ImageDiagramService:

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def generate(
        self,
        image_bytes: bytes,
        dimensions: Optional[PhysicalDimensions] = None,
    ) -> bytes:
        """
        Clothing image + dimensions → Annotated measurement diagram PNG
        """
        # Step 1: Get measurement point coordinates from Gemini
        points = await self._get_measurement_points(image_bytes)

        # Step 2: Draw measurement annotations
        annotated = self._draw_diagram(image_bytes, points, dimensions)

        return annotated

    async def _get_measurement_points(self, image_bytes: bytes) -> dict:
        """
        Gemini Vision দিয়ে garment এর key points detect করে।
        Returns pixel coordinates for each measurement line.
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """Analyze this flat-lay garment image.
Identify key measurement points as percentage coordinates (0-100 of image width/height).

Return ONLY JSON:
{
  "garment_type": "dress|shirt|pants|jacket|skirt|other",
  "measurements": [
    {
      "label": "Chest Width",
      "x1_pct": 25, "y1_pct": 30,
      "x2_pct": 75, "y2_pct": 30,
      "value": "18 in"
    },
    {
      "label": "Back Length",
      "x1_pct": 50, "y1_pct": 10,
      "x2_pct": 50, "y2_pct": 85,
      "value": "38 in"
    },
    {
      "label": "Sleeve Length",
      "x1_pct": 5, "y1_pct": 25,
      "x2_pct": 25, "y2_pct": 50,
      "value": "7 in"
    },
    {
      "label": "Waist Width",
      "x1_pct": 30, "y1_pct": 55,
      "x2_pct": 70, "y2_pct": 55,
      "value": "14 in"
    }
  ]
}
Output ONLY valid JSON."""

        try:
            response = await self.model.generate_content_async([
                {"mime_type": "image/jpeg", "data": image_b64},
                prompt,
            ])
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception:
            # Fallback: standard measurement positions
            return self._default_points()

    def _draw_diagram(
        self,
        image_bytes: bytes,
        points: dict,
        dimensions: Optional[PhysicalDimensions],
    ) -> bytes:
        """
        PIL দিয়ে measurement lines + labels draw করে।
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = img.size

        # Create overlay layer
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Measurement line color — purple (matches Figma theme)
        LINE_COLOR = (138, 43, 226, 220)    # Purple
        ARROW_COLOR = (138, 43, 226, 255)
        TEXT_BG = (255, 255, 255, 230)
        TEXT_COLOR = (40, 40, 40, 255)

        # Override labels with real dimension values if available
        dim_map = {}
        if dimensions:
            dim_map = {
                "Chest Width": f"{dimensions.chest_width_in} in" if dimensions.chest_width_in else None,
                "Back Length": f"{dimensions.back_length_in} in" if dimensions.back_length_in else None,
                "Waist Width": f"{dimensions.waist_width_in} in" if dimensions.waist_width_in else None,
                "Sleeve Length": f"{dimensions.sleeve_length_in} in" if dimensions.sleeve_length_in else None,
                "Under Bust": f"{dimensions.under_bust_in} in" if dimensions.under_bust_in else None,
                "Dress Length": f"{dimensions.dress_length_in} in" if dimensions.dress_length_in else None,
            }

        measurements = points.get("measurements", self._default_points()["measurements"])

        for m in measurements:
            label = m["label"]
            # Convert percentage → pixels
            x1 = int(m["x1_pct"] / 100 * w)
            y1 = int(m["y1_pct"] / 100 * h)
            x2 = int(m["x2_pct"] / 100 * w)
            y2 = int(m["y2_pct"] / 100 * h)

            value = dim_map.get(label) or m.get("value", "")

            # Draw dashed measurement line
            self._draw_dashed_line(draw, x1, y1, x2, y2, LINE_COLOR, width=2)

            # Draw arrowheads
            self._draw_arrowhead(draw, x1, y1, x2, y2, ARROW_COLOR, size=10)
            self._draw_arrowhead(draw, x2, y2, x1, y1, ARROW_COLOR, size=10)

            # Draw label with background
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            text = f"{label}: {value}"
            text_w = len(text) * 6 + 10
            text_h = 20

            # Label background pill
            draw.rounded_rectangle(
                [mid_x - text_w // 2, mid_y - text_h // 2,
                 mid_x + text_w // 2, mid_y + text_h // 2],
                radius=6,
                fill=TEXT_BG,
            )
            draw.text(
                (mid_x - text_w // 2 + 5, mid_y - 7),
                text,
                fill=TEXT_COLOR,
            )

        # Composite
        result = Image.alpha_composite(img, overlay).convert("RGB")
        buf = io.BytesIO()
        result.save(buf, format="PNG")
        return buf.getvalue()

    def _draw_dashed_line(self, draw, x1, y1, x2, y2, color, width=2, dash=8):
        """Dashed line draw করে"""
        import math
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return
        steps = int(length / dash)
        for i in range(0, steps, 2):
            t1 = i / steps
            t2 = min((i + 1) / steps, 1.0)
            sx1, sy1 = int(x1 + dx * t1), int(y1 + dy * t1)
            sx2, sy2 = int(x1 + dx * t2), int(y1 + dy * t2)
            draw.line([(sx1, sy1), (sx2, sy2)], fill=color, width=width)

    def _draw_arrowhead(self, draw, from_x, from_y, to_x, to_y, color, size=10):
        """Arrow tip draw করে"""
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        tip_x = from_x + size * math.cos(angle)
        tip_y = from_y + size * math.sin(angle)
        left_x = from_x + size * math.cos(angle + 2.5)
        left_y = from_y + size * math.sin(angle + 2.5)
        right_x = from_x + size * math.cos(angle - 2.5)
        right_y = from_y + size * math.sin(angle - 2.5)
        draw.polygon(
            [(int(tip_x), int(tip_y)), (int(left_x), int(left_y)), (int(right_x), int(right_y))],
            fill=color,
        )

    def _default_points(self) -> dict:
        return {
            "garment_type": "dress",
            "measurements": [
                {"label": "Chest Width",   "x1_pct": 20, "y1_pct": 28, "x2_pct": 80, "y2_pct": 28, "value": "18 in"},
                {"label": "Back Length",   "x1_pct": 85, "y1_pct": 8,  "x2_pct": 85, "y2_pct": 88, "value": "38 in"},
                {"label": "Waist Width",   "x1_pct": 25, "y1_pct": 55, "x2_pct": 75, "y2_pct": 55, "value": "14 in"},
                {"label": "Sleeve Length", "x1_pct": 5,  "y1_pct": 20, "x2_pct": 20, "y2_pct": 50, "value": "7 in"},
            ],
        }


image_diagram_service = ImageDiagramService()