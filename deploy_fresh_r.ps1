# ========================================
# Fresh-R Deployment Script (Testing Phase)
# Automatically cleans cache and deploys
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Fresh-R Deployment to Home Assistant" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$SourcePath = "custom_components\fresh_r"
$DestPath = "\\192.168.2.5\config\custom_components\fresh_r"

# Step 1: Delete Python cache
Write-Host "[1/4] Cleaning Python cache..." -ForegroundColor Yellow
try {
    Remove-Item -Recurse -Force "$DestPath\__pycache__" -ErrorAction SilentlyContinue
    Write-Host "      ✓ Cache cleaned!" -ForegroundColor Green
} catch {
    Write-Host "      ⚠ Cache already clean or not found" -ForegroundColor Gray
}
Write-Host ""

# Step 2: Copy all Python files
Write-Host "[2/4] Copying Python files..." -ForegroundColor Yellow
Copy-Item "$SourcePath\*.py" $DestPath -Force
Write-Host "      ✓ Python files copied!" -ForegroundColor Green
Write-Host ""

# Step 3: Copy manifest and strings
Write-Host "[3/4] Copying manifest and strings..." -ForegroundColor Yellow
Copy-Item "$SourcePath\manifest.json" $DestPath -Force
Copy-Item "$SourcePath\strings.json" $DestPath -Force
Write-Host "      ✓ Config files copied!" -ForegroundColor Green
Write-Host ""

# Step 4: Copy translations
Write-Host "[4/4] Copying translations..." -ForegroundColor Yellow
Copy-Item "$SourcePath\translations\*.json" "$DestPath\translations\" -Force
Write-Host "      ✓ Translations copied!" -ForegroundColor Green
Write-Host ""

# Verify deployment
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show file info
$apiFile = Get-Item "$DestPath\api.py"
Write-Host "Deployed api.py:" -ForegroundColor White
Write-Host "  Size: $($apiFile.Length) bytes" -ForegroundColor Gray
Write-Host "  Modified: $($apiFile.LastWriteTime)" -ForegroundColor Gray
Write-Host ""

Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Restart Home Assistant" -ForegroundColor White
Write-Host "  2. Wait for HA to come online (~1-2 min)" -ForegroundColor White
Write-Host "  3. Install/Configure Fresh-R integration" -ForegroundColor White
Write-Host ""
