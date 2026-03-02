# 📮 Postman দিয়ে Multi-Image Upload Test

## Step-by-Step Guide:

### 1. Postman Open করুন

### 2. New Request তৈরি করুন:
- Method: **POST**
- URL: `http://localhost:8000/api/v1/generate-batch`

### 3. Body Setup করুন:
- **Body** tab এ যান
- **form-data** select করুন (না হলে x-www-form-urlencoded থেকে dropdown এ form-data select করুন)

### 4. Fields Add করুন:

| KEY | TYPE | VALUE |
|-----|------|-------|
| `seller_id` | Text | `seller_123` |
| `features_json` | Text | `[{"features":["background_removal","model"]},{"features":["physical_dimensions"]}]` |
| `images` | **File** | [Click "Select Files" → Choose image1.jpg] |
| `images` | **File** | [Click "Select Files" → Choose image2.jpg] |
| `images` | **File** | [Click "Select Files" → Choose image3.jpg] |

### 5. Important Notes:

#### ⚠️ `images` field কিভাবে multiple বার add করবেন:
1. First `images` field add করুন → TYPE dropdown থেকে **File** select করুন
2. **Hover করুন** KEY এর পাশে → একটা **duplicate icon** দেখবেন
3. সেই icon click করে field টি duplicate করুন
4. প্রতিটি `images` field এ আলাদা file select করুন

অথবা:
1. নতুন row add করুন
2. KEY: `images` লিখুন
3. TYPE: **File** select করুন
4. VALUE: File select করুন
5. প্রতিটি image এর জন্য repeat করুন

### 6. Send Button Click করুন

### 7. Response দেখবেন:
```json
{
  "product_id": "abc-123-def-456",
  "status": "pending",
  "message": "Batch processing started for 3 images. Poll /status to track progress."
}
```

### 8. Status Check করুন:
- New Request: **GET**
- URL: `http://localhost:8000/api/v1/{product_id}/status`
- Replace `{product_id}` with response এ পাওয়া ID

---

## 🎯 Screenshot Guide:

### Correct Postman Setup Should Look Like This:

```
┌─────────────────────────────────────────────────┐
│ POST http://localhost:8000/api/v1/generate-batch│
├─────────────────────────────────────────────────┤
│ Body: ○ none  ○ form-data  ○ x-www-form...     │
│                   ↑↑↑ Select this              │
├──────────┬──────┬────────────────────────────────┤
│   KEY    │ TYPE │         VALUE                  │
├──────────┼──────┼────────────────────────────────┤
│ ☑ seller_id │Text│ seller_123                  │
│ ☑ features_ │Text│ [{"features":["bg_removal"]}]│
│     json    │    │                               │
│ ☑ images    │File│ [image1.jpg] 📎 Select Files │
│ ☑ images    │File│ [image2.jpg] 📎 Select Files │
│ ☑ images    │File│ [image3.jpg] 📎 Select Files │
└──────────┴──────┴────────────────────────────────┘
              ↑↑↑
          Must be File, 
          not Text!
```

---

## ❌ Common Mistakes:

### 1. TYPE যদি "Text" থাকে:
```
❌ images | Text | "image1.jpg"  ← Wrong!
✅ images | File | [Select File]  ← Correct!
```

### 2. ভুল features_json format:
```
❌ features_json: ["background_removal", "model"]
✅ features_json: [{"features":["background_removal","model"]},{"features":["physical_dimensions"]}]
```

### 3. Features array length ≠ Images count:
```
❌ 2 images but 3 feature objects
✅ 2 images and 2 feature objects
```

---

## 🔧 Alternative: cURL Command

```bash
curl -X POST "http://localhost:8000/api/v1/generate-batch" \
  -F "seller_id=seller_123" \
  -F 'features_json=[{"features":["background_removal"]},{"features":["model"]}]' \
  -F "images=@C:/path/to/image1.jpg" \
  -F "images=@C:/path/to/image2.jpg"
```

**Windows PowerShell:**
```powershell
curl.exe -X POST "http://localhost:8000/api/v1/generate-batch" `
  -F "seller_id=seller_123" `
  -F 'features_json=[{\"features\":[\"background_removal\"]},{\"features\":[\"model\"]}]' `
  -F "images=@C:/path/to/image1.jpg" `
  -F "images=@C:/path/to/image2.jpg"
```
