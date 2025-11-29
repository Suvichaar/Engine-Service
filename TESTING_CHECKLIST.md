# 🧪 Testing Checklist - Story Generation System

## ✅ **COMPLETED TESTS**

### **1. Backend Configuration & Setup**
- ✅ **AI Image Provider**: DALL-E API properly configured and initialized
- ✅ **Voice Synthesis**: Azure TTS configured with correct credentials
- ✅ **CDN URLs Fixed**: 
  - Images: `media.suvichaar.org` ✅
  - Audio: `cdn.suvichaar.org` ✅
- ✅ **Database**: No-op repository working (database disabled for development)

### **2. Category Support**
- ✅ **Education Category**: Added to Curious mode allowed categories
- ✅ **Frontend Dropdown**: Streamlit shows correct categories for each mode
- ✅ **Backend Validation**: Education category accepted in API requests

### **3. Upload Widget & Form Issues**
- ✅ **Custom Images Upload**: Widget appears when "Custom Images" selected
- ✅ **Debug Information**: Request payload shows correct `image_source` values
- ✅ **Image Source Logic**: Fixed `image_source` being `None` instead of `"custom"`
- ✅ **Force Enable**: Temporarily enabled upload widget for testing

### **4. URL Generation & Access**
- ✅ **Curious Mode URLs**: Now use slug-based format like News mode
- ✅ **URL Format Consistency**: Both modes use `suvichaar.org/stories/slug_nano` format
- ✅ **S3 HTML Upload**: Curious mode HTML files now uploaded to S3
- ✅ **API URL Generation**: Backend generates proper slug + nano ID URLs

### **5. AI Image Generation (Backend)**
- ✅ **Direct API Test**: AI images generate successfully via backend API
- ✅ **Alt Text Extraction**: Curious mode uses narrative JSON alt texts
- ✅ **Fallback Prompts**: System handles missing alt texts gracefully
- ✅ **Image Storage**: Generated images uploaded to S3 with correct CDN URLs

### **5a. Custom Image Handling (Backend)**
- ✅ **S3 URI Support**: Custom images from S3 URIs properly extracted and used
- ✅ **CDN URL Generation**: Base64 template URLs generated with `media.suvichaar.org`
- ✅ **No Re-upload**: Original S3 keys preserved, no duplicate uploads
- ✅ **News Mode Custom Images**: Working correctly with proper CDN URLs

---

## 🔄 **TESTS IN PROGRESS / PARTIALLY COMPLETED**

### **6. Template System**
- 🔄 **Mode-Specific Templates**: Curious mode should show `curious-template-1`, `template-v19`
- 🔄 **Template Dropdown**: Need to verify mode switching works correctly
- ❓ **Status**: Fixed in code but needs verification in Streamlit

### **7. CDN URL Verification**
- 🔄 **Image URLs**: Backend generates `media.suvichaar.org` URLs
- 🔄 **Audio URLs**: Backend generates `cdn.suvichaar.org` URLs  
- ❓ **Status**: URLs generated correctly, but need browser testing

---

## ❌ **PENDING TESTS (HIGH PRIORITY)**

### **8. End-to-End Story Generation**
- ✅ **News Mode + Default Images**: Generate story and verify it loads in browser - **COMPLETED** ✅
- ✅ **News Mode + AI Images**: Generate with AI images and verify they appear - **COMPLETED** ✅
- ✅ **News Mode + Custom Images**: Upload custom images and verify backgrounds - **COMPLETED** ✅
  - Custom images from S3 URIs working correctly
  - CDN URLs generated with `media.suvichaar.org` and base64 template format
  - Original S3 keys preserved (no re-upload)
  - Images appear correctly in generated stories
- ✅ **Curious Mode + AI Images**: Generate with AI images and verify they appear - **COMPLETED** ✅
- ✅ **Curious Mode + Pexels Images**: Generate with stock images and verify they appear - **COMPLETED** ✅
- [ ] **Curious Mode + Custom Images**: Upload custom images and verify backgrounds

### **9. Browser Story Access**
- [ ] **News Mode URL Access**: Test `canurl1` opens properly in browser
- [ ] **Curious Mode URL Access**: Test `canurl1` opens properly in browser
- [ ] **Image Loading**: Verify images appear (not gray backgrounds)
- [ ] **Audio Playback**: Verify audio controls work and files play
- [ ] **Mobile Responsiveness**: Test stories on mobile devices

### **10. Streamlit Frontend Integration**
- [ ] **Form Submission**: All input fields work correctly
- [ ] **Template Dropdown**: Mode-specific templates show correctly
- [ ] **Image Upload**: Multiple image upload with graceful handling works
- [ ] **Request Payload**: Verify correct data sent to backend
- [ ] **Error Handling**: Test invalid inputs and API failures

### **11. Multiple Image Upload & Graceful Handling**
- [ ] **Perfect Match**: Upload exact number of images for slide count
- [ ] **Extra Images**: Upload more images than slides (should ignore extras)
- [ ] **Fewer Images**: Upload fewer images than slides (should repeat last)
- [ ] **No Images**: Test behavior with zero custom images
- [ ] **Image Validation**: Test invalid file types and sizes

---

## ❌ **PENDING TESTS (MEDIUM PRIORITY)**

### **12. Content Quality & Generation**
- [ ] **Text Generation**: Stories have proper content and structure
- [ ] **Image Relevance**: AI images match story content appropriately
- [ ] **Audio Quality**: Voice synthesis sounds natural and clear
- [ ] **SEO Metadata**: Meta tags (title, description, keywords) properly generated
- [ ] **Language Support**: Test Hindi vs English content generation

### **13. S3 Storage & CDN**
- [ ] **S3 Upload Verification**: Confirm files actually saved to correct buckets
- [ ] **CDN Access**: Test direct CDN URLs work in browser
- [ ] **File Permissions**: Verify S3 files are publicly accessible
- [ ] **Bucket Organization**: Check files saved to correct folders/prefixes

### **14. API Error Handling**
- ✅ **Invalid Inputs**: System handles bad JSON gracefully - **COMPLETED** ✅
  - Malformed JSON returns 422 Unprocessable Entity
  - Missing required fields return 422 with validation errors
  - Invalid field values return 422 with validation errors
  - Wrong data types return 422 with type validation errors
  - Test script: `test_error_handling.py` (Tests 1.1-1.4)
- [ ] **API Failures**: Proper error messages for DALL-E/TTS failures  
  - DALL-E API failure: Retry 3 times with exponential backoff
  - DALL-E content policy violation: Simpler prompt on retry
  - TTS failure: Story generated, audio might be missing
  - **Testing Method**: Use invalid endpoint URLs (keep real credentials safe)
    - DALL-E: Set `[ai_image] endpoint = "https://invalid-endpoint.com/api"`
    - TTS: Set invalid TTS endpoint URL
  - Test script: `test_error_handling.py` (Tests 2.1-2.4)
  - **Note**: No need to break credentials - just use unreachable endpoints
- [ ] **Network Issues**: Timeout handling for external services
  - httpx timeout (30 seconds) triggers retry
  - Exponential backoff on network failures
  - **Testing Method**: Use unreachable endpoint (e.g., `https://192.0.2.1/api`)
  - Test script: `test_error_handling.py`
  - **Note**: Can use RFC 3330 test IP range (192.0.2.0/24) for unreachable endpoints
- [ ] **S3 Upload Failures**: Fallback behavior when uploads fail
  - S3 upload errors: Story generation continues
  - S3 upload errors logged but don't fail story creation
  - **Testing Method**: Use invalid bucket name (keep real credentials safe)
    - Set `[aws] AWS_BUCKET = "non-existent-bucket-12345"`
  - Test script: `test_error_handling.py` (Test 4.1)
  - **Note**: No need to break credentials - just use non-existent bucket
- ✅ **Database Errors**: System continues working without database - **COMPLETED** ✅
  - Database connection failure: Story generation succeeds
  - Database save errors logged as non-critical
  - Story returned successfully even if database save fails
  - **Testing Method**: Use invalid database URL (e.g., `postgresql://invalid@192.0.2.1:5432/invalid`)
  - Test script: `test_error_handling.py` (Test 5.1)
  - **Note**: Safe to test - credentials not needed, just unreachable URL

---

## ❌ **PENDING TESTS (LOW PRIORITY)**

### **15. Performance & Scalability**
- [ ] **Generation Speed**: Time story generation end-to-end
- [ ] **Concurrent Requests**: Test multiple simultaneous story generations
- [ ] **Memory Usage**: Monitor resource consumption during generation
- [ ] **Large Files**: Test with large attachment uploads

### **16. Security & Validation**
- [ ] **Input Sanitization**: Test XSS and injection attempts
- [ ] **File Upload Security**: Test malicious file uploads
- [ ] **API Rate Limiting**: Test excessive request handling
- [ ] **Credential Security**: Verify no secrets exposed in responses

### **17. Edge Cases & Robustness**
- [ ] **Empty Content**: Test with minimal/empty user input
- [ ] **Special Characters**: Test Unicode, emojis, special symbols
- [ ] **Long Content**: Test with very long articles/text
- [ ] **Network Interruptions**: Test partial failures and recovery

---

## 🎯 **IMMEDIATE NEXT STEPS**

### **Priority 1: Browser Testing**
1. Generate a Curious mode story via Streamlit
2. Copy the `canurl1` URL
3. Open in browser and verify:
   - Story loads without errors
   - Images appear (not gray)
   - Audio controls present
   - Content is readable

### **Priority 2: Template Dropdown**
1. Open Streamlit frontend
2. Switch between News and Curious modes
3. Verify template dropdown updates correctly
4. Test story generation with different templates

### **Priority 3: Image Upload Testing**
1. Test custom image upload for both modes
2. Verify graceful handling (extra/fewer images)
3. Check image previews and validation messages

---

## 🔧 **Test Commands & URLs**

### **Streamlit Frontend**
```
http://localhost:8501
```

### **Backend API**
```bash
# Test Curious mode with AI images
$body = @{
    mode = "curious"
    template_key = "curious-template-1"
    slide_count = 7
    user_input = "How does quantum computing work?"
    category = "Education"
    image_source = "ai"
    prompt_keywords = @("quantum", "computing", "science")
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```

### **News Mode Test**
```bash
$body = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    user_input = "https://example.com/news-article"
    category = "Technology"
    image_source = $null
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```

---

## 📊 **Progress Summary**

- **✅ Completed**: 7 major areas (Configuration, Categories, Upload Widget, URLs, AI Images, Custom Images, Error Handling - Partial)
- **🔄 In Progress**: 2 areas (Templates, CDN Verification)  
- **❌ Pending**: 8 major areas (End-to-End partially done, Browser Access, Frontend, etc.)
- **Overall Progress**: ~50% complete

**Recent Achievements**: 
- ✅ News Mode + Custom Images working correctly with proper CDN URLs!
- ✅ News Mode + Default Images verified in browser
- ✅ News Mode + AI Images working correctly
- ✅ Curious Mode + AI Images working correctly
- ✅ Curious Mode + Pexels Images working correctly
- ✅ API Error Handling - Invalid Inputs tested and working correctly
- ✅ API Error Handling - Database Errors tested and working correctly

**Next milestone: Complete advanced error handling tests (API failures, S3 upload failures) using safe methods (invalid endpoints/URLs, not credentials) and browser story access verification.**

**Testing Tip**: For error handling tests, use invalid endpoints/URLs instead of breaking credentials. This is safer and easier to restore.
