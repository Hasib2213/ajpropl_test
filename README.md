# ResaleAI — Fashion AI Backend

> "Upload a garment photo. AI handles the rest."

---

## 📁 File Structure

```
fashion_ai/
│
├── main.py                          # FastAPI app entry point
├── requirements.txt                 # Dependencies
├── .env.example                     # Environment variables template
│
├── config/
│   ├── settings.py                  # All settings (Pydantic)
│   └── database.py                  # MongoDB connection + collections
│
├── models/
│   └── product.py                   # All schemas (ProductInDB, request/response)
│
├── services/
│   ├── pipeline.py                  # ⭐ Main orchestrator — runs all features
│   ├── product_listing.py           # Gemini → Title, description, tags
│   │
│   └── features/                    # 6 AI Features
│       ├── physical_dimensions.py   # Feature 1 — Gemini Vision → measurements
│       ├── background_removal.py    # Feature 2 — Remove.bg API
│       ├── virtual_tryon.py         # Feature 3 — Replicate IDM-VTON
│       ├── image_diagram.py         # Feature 4 — Gemini + Pillow → annotated diagram
│       ├── mannequin.py             # Feature 5 — Replicate SDXL → ghost mannequin
│       └── model.py                 # Feature 6 — Replicate IDM-VTON → on-model photo
│
├── routers/
│   └── products.py                  # All API endpoints
│
└── utils/
    ├── storage.py                   # Cloudflare R2 upload/delete
    └── http.py                      # HTTP helpers
```

---

## 🤖 6 AI Features

| # | Feature | How | API |
|---|---------|-----|-----|
| 1 | **Physical Dimensions** | Detects measurements from flat-lay image | Gemini Vision |
| 2 | **Background Removal** | Removes background, white/transparent output | Remove.bg |
| 3 | **AI Virtual Try-On** | Puts clothing on realistic human model | Replicate (IDM-VTON) |
| 4 | **Image Diagram** | Draws measurement arrows/labels on clothing | Gemini + Pillow |
| 5 | **Mannequin** | Ghost mannequin / invisible mannequin effect | Replicate (SDXL) |
| 6 | **Model** | Diverse model poses wearing the clothing | Replicate (IDM-VTON) |

---

## 🔄 How It Works (Figma Flow)

```
Step 1 — Upload
  Seller uploads flat-lay garment image
  Selects which of 6 features to run
  Clicks "Generate"

Step 2 — AI Processing (parallel)
  All selected features run simultaneously
  Background removal → feeds into Try-On, Mannequin, Model
  Gemini generates measurements + product listing

Step 3 — Verification
  Seller reviews output
  Can edit title, description, price, tags
  Can regenerate any section

Step 4 — Auto-List
  Product ready to publish
  Download or Save to Google Drive
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/products/generate` | Upload image + select features → start processing |
| `GET` | `/api/v1/products/{id}/status` | Check processing status (poll this) |
| `GET` | `/api/v1/products/{id}` | Get full product listing |
| `PATCH` | `/api/v1/products/{id}` | Edit product fields (verification step) |
| `POST` | `/api/v1/products/{id}/publish` | Mark ready + set price/SKU |
| `GET` | `/api/v1/products/seller/{id}` | Get all seller products |
| `DELETE` | `/api/v1/products/{id}` | Delete product |

---

## 🚀 Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy env file
cp .env.example .env
# Fill in your API keys

# 3. Run
uvicorn main:app --reload --port 8000

# 4. API Docs
open http://localhost:8000/docs
```

---

## 🔑 API Keys Needed

| Key | From |
|-----|------|
| `GEMINI_API_KEY` | https://aistudio.google.com |
| `REMOVEBG_API_KEY` | https://remove.bg/api |
| `REPLICATE_API_TOKEN` | https://replicate.com |
| `GOOGLE_VISION_API_KEY` | https://console.cloud.google.com |
| `R2_*` | https://dash.cloudflare.com |

---

## 💰 Cost Per Product

| Feature | API | Cost |
|---------|-----|------|
| Physical Dimensions | Gemini Flash | ~$0.001 |
| Background Removal | Remove.bg | ~$0.02 |
| Virtual Try-On | Replicate | ~$0.05-0.10 |
| Image Diagram | Gemini + Pillow | ~$0.001 |
| Mannequin | Replicate SDXL | ~$0.02-0.05 |
| Model | Replicate IDM-VTON | ~$0.05-0.10 |
| Product Listing | Gemini Flash | ~$0.001 |
| **Total (all features)** | | **~$0.15-0.30** |

---

## 📦 MongoDB Collections

```
resale_ai/
├── products      — Main product documents
└── jobs          — Processing job tracking
```

### Product Document Structure
```json
{
  "_id": "uuid",
  "seller_id": "seller_001",
  "status": "completed",
  "selected_features": ["background_removal", "model", "physical_dimensions"],
  "product_title": "Women's Floral Summer Dress",
  "description": "...",
  "product_details": {
    "category": "Women > Dresses",
    "brand": "Local Designer",
    "sleeve_length": "Short",
    "dress_type": "A-line",
    "age_group": "18-35",
    "gender": "Female"
  },
  "dimensions": {
    "chest_width_in": 18.0,
    "back_length_in": 38.0,
    "waist_width_in": 14.0,
    "sleeve_length_in": 7.0,
    "under_bust_in": 13.0,
    "dress_length_in": 40.0
  },
  "variant_data": {
    "sizes": ["S", "M", "L", "XL"],
    "colors": ["Blue", "Pink"],
    "condition": "New",
    "feature": "Floral print"
  },
  "tags": ["vintage", "cotton", "casual", "summer"],
  "images": {
    "original_url": "https://...",
    "background_removed_url": "https://...",
    "virtual_tryon_urls": ["https://...", "https://..."],
    "image_diagram_url": "https://...",
    "mannequin_urls": ["https://...", "https://..."],
    "model_urls": ["https://...", "https://..."]
  },
  "storage": {
    "google_drive_folder": "/AutoList/Processed/",
    "auto_listing_enabled": true,
    "last_processed": "2025-01-18T14:32:00Z"
  },
  "sku": "SKU-000123456789",
  "ready_to_publish": true
}
```