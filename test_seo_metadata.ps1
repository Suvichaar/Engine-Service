# Test Script for SEO Metadata and Placeholders
# Tests both Curious and News modes and verifies all placeholders

Write-Host "`n=== 🧪 Testing Story Generation API ===" -ForegroundColor Cyan
Write-Host "`nMake sure the server is running on http://localhost:8000" -ForegroundColor Yellow

$baseUrl = "http://localhost:8000"

# Test 1: Curious Mode
Write-Host "`n[1/2] Testing Curious Mode..." -ForegroundColor Green
$curiousBody = @{
    mode = "curious"
    template_key = "curious-template-1"
    slide_count = 7
    user_input = "How does quantum computing work? Explain the basic principles, quantum bits (qubits), superposition, and entanglement."
    image_source = "ai"
    prompt_keywords = @("quantum", "computing", "science", "technology", "physics")
    voice_engine = "azure_basic"
} | ConvertTo-Json -Depth 10

try {
    $curiousResponse = Invoke-RestMethod -Uri "$baseUrl/stories" `
        -Method POST `
        -ContentType "application/json" `
        -Body $curiousBody
    
    Write-Host "✅ Curious Mode Story Created!" -ForegroundColor Green
    Write-Host "   Story ID: $($curiousResponse.id)" -ForegroundColor White
    Write-Host "   Mode: $($curiousResponse.mode)" -ForegroundColor White
    Write-Host "   Template: $($curiousResponse.template_key)" -ForegroundColor White
    Write-Host "   Slide Count: $($curiousResponse.slide_count)" -ForegroundColor White
    
    # Check HTML file
    $htmlPath = "output\$($curiousResponse.id).html"
    if (Test-Path $htmlPath) {
        Write-Host "`n   📄 HTML File: $htmlPath" -ForegroundColor Cyan
        $htmlContent = Get-Content $htmlPath -Raw
        
        # Verify placeholders
        Write-Host "`n   🔍 Verifying Placeholders:" -ForegroundColor Cyan
        
        # Check title
        if ($htmlContent -match '<title>([^<]+)</title>') {
            $title = $matches[1]
            if ($title -notmatch '\{\{') {
                Write-Host "   ✅ Title: $($title.Substring(0, [Math]::Min(60, $title.Length)))..." -ForegroundColor Green
            } else {
                Write-Host "   ❌ Title placeholder not replaced: $title" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Title tag not found" -ForegroundColor Red
        }
        
        # Check meta description
        if ($htmlContent -match '<meta\s+name="description"\s+content="([^"]+)"') {
            $metaDesc = $matches[1]
            if ($metaDesc -notmatch '\{\{') {
                Write-Host "   ✅ Meta Description: $($metaDesc.Substring(0, [Math]::Min(60, $metaDesc.Length)))..." -ForegroundColor Green
            } else {
                Write-Host "   ❌ Meta description placeholder not replaced" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Meta description not found" -ForegroundColor Red
        }
        
        # Check meta keywords
        if ($htmlContent -match '<meta\s+name="keywords"\s+content="([^"]+)"') {
            $metaKeywords = $matches[1]
            if ($metaKeywords -notmatch '\{\{') {
                Write-Host "   ✅ Meta Keywords: $($metaKeywords.Substring(0, [Math]::Min(60, $metaKeywords.Length)))..." -ForegroundColor Green
            } else {
                Write-Host "   ❌ Meta keywords placeholder not replaced" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Meta keywords not found" -ForegroundColor Red
        }
        
        # Check lang
        if ($htmlContent -match '<html[^>]*lang="([^"]+)"') {
            $lang = $matches[1]
            if ($lang -match '^(en-US|hi-IN)$') {
                Write-Host "   ✅ Lang: $lang (correct format)" -ForegroundColor Green
            } elseif ($lang -notmatch '\{\{') {
                Write-Host "   ⚠️  Lang: $lang (should be en-US or hi-IN)" -ForegroundColor Yellow
            } else {
                Write-Host "   ❌ Lang placeholder not replaced" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Lang attribute not found" -ForegroundColor Red
        }
        
        # Check contenttype
        if ($htmlContent -match '<meta\s+property="og:type"\s+content="([^"]+)"') {
            $contentType = $matches[1]
            if ($contentType -eq "Article") {
                Write-Host "   ✅ Content Type: $contentType (correct for Curious mode)" -ForegroundColor Green
            } elseif ($contentType -notmatch '\{\{') {
                Write-Host "   ⚠️  Content Type: $contentType (expected: Article)" -ForegroundColor Yellow
            } else {
                Write-Host "   ❌ Content type placeholder not replaced" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Content type not found" -ForegroundColor Red
        }
        
        # Check published time
        if ($htmlContent -match '<meta\s+property="article:published_time"\s+content="([^"]+)"') {
            $pubTime = $matches[1]
            if ($pubTime -match '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}') {
                Write-Host "   ✅ Published Time: $pubTime (ISO format)" -ForegroundColor Green
            } elseif ($pubTime -notmatch '\{\{') {
                Write-Host "   ⚠️  Published Time: $pubTime (should be ISO format)" -ForegroundColor Yellow
            } else {
                Write-Host "   ❌ Published time placeholder not replaced" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Published time not found" -ForegroundColor Red
        }
        
        # Check modified time
        if ($htmlContent -match '<meta\s+property="article:modified_time"\s+content="([^"]+)"') {
            $modTime = $matches[1]
            if ($modTime -match '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}') {
                Write-Host "   ✅ Modified Time: $modTime (ISO format)" -ForegroundColor Green
            } elseif ($modTime -notmatch '\{\{') {
                Write-Host "   ⚠️  Modified Time: $modTime (should be ISO format)" -ForegroundColor Yellow
            } else {
                Write-Host "   ❌ Modified time placeholder not replaced" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Modified time not found" -ForegroundColor Red
        }
        
        # Check for any remaining placeholders
        $remainingPlaceholders = [regex]::Matches($htmlContent, '\{\{[^}]+\}\}') | ForEach-Object { $_.Value } | Select-Object -Unique
        if ($remainingPlaceholders.Count -gt 0) {
            Write-Host "`n   ⚠️  Remaining placeholders found:" -ForegroundColor Yellow
            $remainingPlaceholders | ForEach-Object { Write-Host "      - $_" -ForegroundColor Yellow }
        } else {
            Write-Host "`n   ✅ No remaining placeholders found" -ForegroundColor Green
        }
        
    } else {
        Write-Host "   ⚠️  HTML file not found at: $htmlPath" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "   ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host "   Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# Test 2: News Mode
Write-Host "`n[2/2] Testing News Mode..." -ForegroundColor Green
$newsBody = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    user_input = "Breaking news: Technology breakthrough in artificial intelligence research"
    image_source = "pexels"
    prompt_keywords = @("technology", "AI", "news", "innovation")
    voice_engine = "azure_basic"
    category = "Technology"
} | ConvertTo-Json -Depth 10

try {
    $newsResponse = Invoke-RestMethod -Uri "$baseUrl/stories" `
        -Method POST `
        -ContentType "application/json" `
        -Body $newsBody
    
    Write-Host "✅ News Mode Story Created!" -ForegroundColor Green
    Write-Host "   Story ID: $($newsResponse.id)" -ForegroundColor White
    Write-Host "   Mode: $($newsResponse.mode)" -ForegroundColor White
    Write-Host "   Template: $($newsResponse.template_key)" -ForegroundColor White
    Write-Host "   Slide Count: $($newsResponse.slide_count)" -ForegroundColor White
    
    # Check HTML file
    $htmlPath = "output\$($newsResponse.id).html"
    if (Test-Path $htmlPath) {
        Write-Host "`n   📄 HTML File: $htmlPath" -ForegroundColor Cyan
        $htmlContent = Get-Content $htmlPath -Raw
        
        # Verify placeholders
        Write-Host "`n   🔍 Verifying Placeholders:" -ForegroundColor Cyan
        
        # Check contenttype (should be "News" for News mode)
        if ($htmlContent -match '<meta\s+property="og:type"\s+content="([^"]+)"') {
            $contentType = $matches[1]
            if ($contentType -eq "News") {
                Write-Host "   ✅ Content Type: $contentType (correct for News mode)" -ForegroundColor Green
            } elseif ($contentType -notmatch '\{\{') {
                Write-Host "   ⚠️  Content Type: $contentType (expected: News)" -ForegroundColor Yellow
            } else {
                Write-Host "   ❌ Content type placeholder not replaced" -ForegroundColor Red
            }
        } else {
            Write-Host "   ❌ Content type not found" -ForegroundColor Red
        }
        
        # Check other placeholders (same as Curious mode)
        if ($htmlContent -match '<title>([^<]+)</title>') {
            $title = $matches[1]
            if ($title -notmatch '\{\{') {
                Write-Host "   ✅ Title: $($title.Substring(0, [Math]::Min(60, $title.Length)))..." -ForegroundColor Green
            }
        }
        
        if ($htmlContent -match '<meta\s+name="description"\s+content="([^"]+)"') {
            $metaDesc = $matches[1]
            if ($metaDesc -notmatch '\{\{') {
                Write-Host "   ✅ Meta Description: $($metaDesc.Substring(0, [Math]::Min(60, $metaDesc.Length)))..." -ForegroundColor Green
            }
        }
        
        if ($htmlContent -match '<meta\s+name="keywords"\s+content="([^"]+)"') {
            $metaKeywords = $matches[1]
            if ($metaKeywords -notmatch '\{\{') {
                Write-Host "   ✅ Meta Keywords: $($metaKeywords.Substring(0, [Math]::Min(60, $metaKeywords.Length)))..." -ForegroundColor Green
            }
        }
        
    } else {
        Write-Host "   ⚠️  HTML file not found at: $htmlPath" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "   ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host "   Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host "`n=== ✅ Testing Complete ===" -ForegroundColor Cyan
Write-Host "`nCheck the output/ folder for generated HTML files" -ForegroundColor Yellow

