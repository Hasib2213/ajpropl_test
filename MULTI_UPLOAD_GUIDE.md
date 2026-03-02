# Multi-Image Upload Guide

## 🚀 `/api/v1/generate-batch` - Multiple File Upload

### 📮 1. Postman থেকে Upload:

```
1. New Request → POST
2. URL: http://localhost:8000/api/v1/generate-batch
3. Body → form-data (select)
4. Add fields:

   KEY              TYPE    VALUE
   ─────────────────────────────────────────────────────────────
   seller_id        Text    seller_123
   
   features_json    Text    [{"features":["background_removal","model"]},{"features":["physical_dimensions"]}]
   
   images           File    [Select file 1.jpg]
   images           File    [Select file 2.jpg]
   images           File    [Select file 3.jpg]

5. Send → Response পাবেন product_id সহ
```

**Important:** `images` field একাধিকবার add করতে হবে প্রতিটি image এর জন্য।

---

### 🌐 2. HTML Form থেকে Upload:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Batch Upload Test</title>
</head>
<body>
    <h2>Multi-Image Upload</h2>
    <form id="uploadForm">
        <label>Seller ID:</label>
        <input type="text" name="seller_id" value="seller_123" required><br><br>
        
        <label>Features JSON:</label>
        <textarea name="features_json" rows="3" cols="50" required>
[
  {"features": ["background_removal", "model"]},
  {"features": ["physical_dimensions"]}
]
        </textarea><br><br>
        
        <label>Select Images (multiple):</label>
        <input type="file" name="images" multiple accept="image/jpeg,image/png,image/webp" required><br><br>
        
        <button type="submit">Upload</button>
    </form>

    <div id="result"></div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            
            try {
                const response = await fetch('http://localhost:8000/api/v1/generate-batch', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                document.getElementById('result').innerHTML = 
                    `<pre>${JSON.stringify(result, null, 2)}</pre>`;
            } catch (error) {
                document.getElementById('result').innerHTML = 
                    `<p style="color:red">Error: ${error.message}</p>`;
            }
        });
    </script>
</body>
</html>
```

Save as `test_upload.html` → Open in browser → Test upload

---

### ⚛️ 3. React/JavaScript থেকে Upload:

```javascript
async function uploadMultipleImages(files, sellerId, featuresArray) {
    const formData = new FormData();
    
    // Add seller_id
    formData.append('seller_id', sellerId);
    
    // Add features_json
    formData.append('features_json', JSON.stringify(featuresArray));
    
    // Add multiple images
    for (let i = 0; i < files.length; i++) {
        formData.append('images', files[i]);
    }
    
    try {
        const response = await fetch('http://localhost:8000/api/v1/generate-batch', {
            method: 'POST',
            body: formData
            // Don't set Content-Type header - browser will set it automatically with boundary
        });
        
        const result = await response.json();
        console.log('Upload successful:', result);
        return result;
    } catch (error) {
        console.error('Upload failed:', error);
        throw error;
    }
}

// Usage Example:
const fileInput = document.querySelector('input[type="file"]');
fileInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    
    const features = [
        { features: ["background_removal", "model"] },
        { features: ["physical_dimensions"] }
    ];
    
    const result = await uploadMultipleImages(files, 'seller_123', features);
    console.log('Product ID:', result.product_id);
});
```

---

### 🐍 4. Python (requests) থেকে Upload:

```python
import requests

url = "http://localhost:8000/api/v1/generate-batch"

# Prepare data
data = {
    'seller_id': 'seller_123',
    'features_json': '[{"features":["background_removal","model"]},{"features":["physical_dimensions"]}]'
}

# Prepare files (multiple images)
files = [
    ('images', ('image1.jpg', open('path/to/image1.jpg', 'rb'), 'image/jpeg')),
    ('images', ('image2.jpg', open('path/to/image2.jpg', 'rb'), 'image/jpeg')),
    ('images', ('image3.jpg', open('path/to/image3.jpg', 'rb'), 'image/jpeg')),
]

# Send request
response = requests.post(url, data=data, files=files)
print(response.json())

# Close files
for _, (_, file_obj, _) in files:
    file_obj.close()
```

---

### 🔧 5. cURL থেকে Upload:

```bash
curl -X POST "http://localhost:8000/api/v1/generate-batch" \
  -F "seller_id=seller_123" \
  -F 'features_json=[{"features":["background_removal","model"]},{"features":["physical_dimensions"]}]' \
  -F "images=@/path/to/image1.jpg" \
  -F "images=@/path/to/image2.jpg" \
  -F "images=@/path/to/image3.jpg"
```

---

## ⚠️ Important Notes:

1. **Content-Type:** Request এ `multipart/form-data` automatically set হয়
2. **Field Name:** All images must use same field name: `images`
3. **Order:** Features array এর order = Images array এর order
4. **Max Files:** 20টি image maximum
5. **Max Size:** প্রতি image 50MB পর্যন্ত
6. **Formats:** JPG, PNG, WebP only

---

## 📊 Response Example:

```json
{
  "product_id": "abc-123-def-456",
  "status": "pending",
  "message": "Batch processing started for 3 images. Poll /status to track progress."
}
```

তারপর এই product_id দিয়ে status check করুন:
```
GET /api/v1/abc-123-def-456/status
```
