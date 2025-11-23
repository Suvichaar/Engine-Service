# Test Script for URL Generation and SEO Metadata
# Tests News mode URL generation (slug + nano ID) and Curious mode (UUID)

Write-Host "`n=== 🧪 Testing Story Generation with URL Generation ===" -ForegroundColor Cyan
Write-Host "`nMake sure the server is running on http://localhost:8000" -ForegroundColor Yellow

$baseUrl = "http://localhost:8000"

# Test 1: News Mode (with title-based URL generation)
Write-Host "`n[1/2] Testing News Mode (Title-based URL generation)..." -ForegroundColor Green
$newsBody = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    user_input = "Breaking news: Technology breakthrough in artificial intelligence research"
    image_source = $null  # News mode: null = default images, "custom" = custom images
    voice_engine = "azure_basic"
    category = "Technology"
} | ConvertTo-Json -Depth 10

try {
    Write-Host "   Sending request..." -ForegroundColor Yellow
    $newsResponse = Invoke-RestMethod -Uri "$baseUrl/stories" `
        -Method POST `
        -ContentType "application/json" `
        -Body $newsBody
    
    Write-Host "   ✅ News Mode Story Created!" -ForegroundColor Green
    Write-Host "`n   📋 Story Details:" -ForegroundColor Cyan
    Write-Host "      Story ID: $($newsResponse.id)" -ForegroundColor White
    Write-Host "      Mode: $($newsResponse.mode)" -ForegroundColor White
    Write-Host "      Template: $($newsResponse.template_key)" -ForegroundColor White
    Write-Host "      Slide Count: $($newsResponse.slide_count)" -ForegroundColor White
    
    # Check URLs
    Write-Host "`n   🔗 URL Generation:" -ForegroundColor Cyan
    if ($newsResponse.canurl) {
        Write-Host "      canurl: $($newsResponse.canurl)" -ForegroundColor White
        # Verify format: should be https://suvichaar.org/stories/slug_nano (no .html)
        if ($newsResponse.canurl -match '^https://suvichaar\.org/stories/[a-z0-9-]+_[A-Za-z0-9_-]+_G$') {
            Write-Host "      ✅ canurl format is correct (slug + nano ID, no .html)" -ForegroundColor Green
        } else {
            Write-Host "      ⚠️  canurl format may not match expected pattern" -ForegroundColor Yellow
        }
    } else {
        Write-Host "      ❌ canurl is missing" -ForegroundColor Red
    }
    
    if ($newsResponse.canurl1) {
        Write-Host "      canurl1: $($newsResponse.canurl1)" -ForegroundColor White
        # Verify format: should be https://stories.suvichaar.org/slug_nano.html
        if ($newsResponse.canurl1 -match '^https://stories\.suvichaar\.org/[a-z0-9-]+_[A-Za-z0-9_-]+_G\.html$') {
            Write-Host "      ✅ canurl1 format is correct (slug + nano ID + .html)" -ForegroundColor Green
        } else {
            Write-Host "      ⚠️  canurl1 format may not match expected pattern" -ForegroundColor Yellow
        }
    } else {
        Write-Host "      ❌ canurl1 is missing" -ForegroundColor Red
    }
    
    # Extract slug from URL to verify
    if ($newsResponse.canurl1) {
        if ($newsResponse.canurl1 -match '/([a-z0-9-]+)_([A-Za-z0-9_-]+_G)\.html$') {
            $slug = $matches[1]
            $nano = $matches[2]
            Write-Host "`n   📝 URL Components:" -ForegroundColor Cyan
            Write-Host "      Slug: $slug" -ForegroundColor White
            Write-Host "      Nano ID: $nano" -ForegroundColor White
        }
    }
    
    # Check HTML file
    $htmlPath = "output\$($newsResponse.id).html"
    if (Test-Path $htmlPath) {
        Write-Host "`n   📄 HTML File: $htmlPath" -ForegroundColor Cyan
        $htmlContent = Get-Content $htmlPath -Raw
        
        # Verify placeholders in HTML
        Write-Host "`n   🔍 Verifying Placeholders in HTML:" -ForegroundColor Cyan
        
        # Check canurl in HTML
        if ($htmlContent -match '<meta\s+property="og:url"\s+content="([^"]+)"') {
            $ogUrl = $matches[1]
            Write-Host "      OG URL: $ogUrl" -ForegroundColor White
            if ($ogUrl -eq $newsResponse.canurl) {
                Write-Host "      ✅ OG URL matches canurl" -ForegroundColor Green
            }
        }
        
        # Check canonical URL
        if ($htmlContent -match '<link\s+rel="canonical"\s+href="([^"]+)"') {
            $canonical = $matches[1]
            Write-Host "      Canonical: $canonical" -ForegroundColor White
        }
        
        # Check title
        if ($htmlContent -match '<title>([^<]+)</title>') {
            $title = $matches[1]
            if ($title -notmatch '\{\{') {
                Write-Host "      ✅ Title: $($title.Substring(0, [Math]::Min(60, $title.Length)))..." -ForegroundColor Green
            }
        }
        
        # Check meta description
        if ($htmlContent -match '<meta\s+name="description"\s+content="([^"]+)"') {
            $metaDesc = $matches[1]
            if ($metaDesc -notmatch '\{\{') {
                Write-Host "      ✅ Meta Description: $($metaDesc.Substring(0, [Math]::Min(60, $metaDesc.Length)))..." -ForegroundColor Green
            }
        }
        
        # Check meta keywords
        if ($htmlContent -match '<meta\s+name="keywords"\s+content="([^"]+)"') {
            $metaKeywords = $matches[1]
            if ($metaKeywords -notmatch '\{\{') {
                Write-Host "      ✅ Meta Keywords: $($metaKeywords.Substring(0, [Math]::Min(60, $metaKeywords.Length)))..." -ForegroundColor Green
            }
        }
        
        # Check lang
        if ($htmlContent -match '<html[^>]*lang="([^"]+)"') {
            $lang = $matches[1]
            if ($lang -match '^(en-US|hi-IN)$') {
                Write-Host "      ✅ Lang: $lang" -ForegroundColor Green
            }
        }
        
        # Check contenttype
        if ($htmlContent -match '<meta\s+property="og:type"\s+content="([^"]+)"') {
            $contentType = $matches[1]
            if ($contentType -eq "News") {
                Write-Host "      ✅ Content Type: $contentType (correct for News mode)" -ForegroundColor Green
            }
        }
        
        # Check image URLs
        if ($htmlContent -match '<meta\s+property="og:image"\s+content="([^"]+)"') {
            $ogImage = $matches[1]
            Write-Host "      ✅ OG Image: $ogImage" -ForegroundColor Green
        }
        
    } else {
        Write-Host "`n   ⚠️  HTML file not found at: $htmlPath" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "   ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host "   Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    Write-Host "   Full Error: $_" -ForegroundColor Red
}

# Test 2: Curious Mode (UUID-based URL)
Write-Host "`n[2/2] Testing Curious Mode (UUID-based URL)..." -ForegroundColor Green
$curiousBody = @{
    mode = "curious"
    template_key = "curious-template-1"
    slide_count = 7
    user_input = "How does quantum computing work? Explain the basic principles."
    image_source = "ai"
    prompt_keywords = @("quantum", "computing", "science")
    voice_engine = "azure_basic"
} | ConvertTo-Json -Depth 10

try {
    Write-Host "   Sending request..." -ForegroundColor Yellow
    $curiousResponse = Invoke-RestMethod -Uri "$baseUrl/stories" `
        -Method POST `
        -ContentType "application/json" `
        -Body $curiousBody
    
    Write-Host "   ✅ Curious Mode Story Created!" -ForegroundColor Green
    Write-Host "`n   📋 Story Details:" -ForegroundColor Cyan
    Write-Host "      Story ID: $($curiousResponse.id)" -ForegroundColor White
    Write-Host "      Mode: $($curiousResponse.mode)" -ForegroundColor White
    
    # Check URLs (should be UUID-based)
    Write-Host "`n   🔗 URL Generation:" -ForegroundColor Cyan
    if ($curiousResponse.canurl) {
        Write-Host "      canurl: $($curiousResponse.canurl)" -ForegroundColor White
        # Should contain UUID
        if ($curiousResponse.canurl -match $curiousResponse.id) {
            Write-Host "      ✅ canurl contains story ID (UUID format)" -ForegroundColor Green
        }
    }
    
    if ($curiousResponse.canurl1) {
        Write-Host "      canurl1: $($curiousResponse.canurl1)" -ForegroundColor White
    }
    
} catch {
    Write-Host "   ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host "   Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host "`n=== ✅ Testing Complete ===" -ForegroundColor Cyan
Write-Host "`n📝 Summary:" -ForegroundColor Cyan
Write-Host "- News mode: Should use slug + nano ID format for URLs" -ForegroundColor White
Write-Host "- Curious mode: Should use UUID format for URLs" -ForegroundColor White
Write-Host "- Check output/ folder for generated HTML files" -ForegroundColor White

