# Test script to verify GitHub API functionality
# This script tests the GitHub API calls used in the launcher

Write-Host "Testing GitHub API functionality..." -ForegroundColor Green

# GitHub API configuration
$GITHUB_REPO = "team-slide/Y1-helper"
$GITHUB_API_BASE = "https://api.github.com"
$GITHUB_TOKEN = "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"
$VERSION_FILE = "version.txt"

try {
    $headers = @{
        'Accept' = 'application/vnd.github.v3+json'
        'User-Agent' = 'Y1-Helper-Launcher-Test'
        'Authorization' = "token $GITHUB_TOKEN"
    }
    
    $url = "$GITHUB_API_BASE/repos/$GITHUB_REPO/releases/latest"
    Write-Host "Testing API call to: $url" -ForegroundColor Yellow
    
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    
    Write-Host "Success! Latest release: $($response.tag_name)" -ForegroundColor Green
    Write-Host "Release name: $($response.name)" -ForegroundColor Cyan
    Write-Host "Published: $($response.published_at)" -ForegroundColor Cyan
    
    # Check current version
    Write-Host "`nVersion Check:" -ForegroundColor Yellow
    if (Test-Path $VERSION_FILE) {
        $currentVersion = Get-Content $VERSION_FILE -Raw
        $currentVersion = $currentVersion.Trim()
        Write-Host "  Current version: $currentVersion" -ForegroundColor White
        
        $latestVersion = $response.tag_name.TrimStart('v')
        Write-Host "  Latest version: $latestVersion" -ForegroundColor White
        
        # Simple version comparison
        $currentParts = $currentVersion.Split('.') | ForEach-Object { [int]$_ }
        $latestParts = $latestVersion.Split('.') | ForEach-Object { [int]$_ }
        
        $maxLength = [Math]::Max($currentParts.Length, $latestParts.Length)
        $currentParts = $currentParts + @(0) * ($maxLength - $currentParts.Length)
        $latestParts = $latestParts + @(0) * ($maxLength - $latestParts.Length)
        
        $needsUpdate = $false
        for ($i = 0; $i -lt $maxLength; $i++) {
            if ($latestParts[$i] -gt $currentParts[$i]) {
                $needsUpdate = $true
                break
            } elseif ($latestParts[$i] -lt $currentParts[$i]) {
                break
            }
        }
        
        if ($needsUpdate) {
            Write-Host "  ✓ Update available!" -ForegroundColor Green
        } else {
            Write-Host "  ✓ Version is up to date" -ForegroundColor Green
        }
    } else {
        Write-Host "  No version file found" -ForegroundColor Yellow
    }
    
    Write-Host "`nRelease assets:" -ForegroundColor Yellow
    foreach ($asset in $response.assets) {
        Write-Host "  - $($asset.name) ($($asset.size) bytes)" -ForegroundColor White
    }
    
    # Check for requirements.txt
    $requirementsAsset = $response.assets | Where-Object { $_.name -eq "requirements.txt" }
    if ($requirementsAsset) {
        Write-Host "`n✓ requirements.txt found in release" -ForegroundColor Green
        Write-Host "  Download URL: $($requirementsAsset.browser_download_url)" -ForegroundColor Cyan
    } else {
        Write-Host "`n✗ requirements.txt not found in release" -ForegroundColor Yellow
    }
    
    # Check for executable
    $exeAsset = $response.assets | Where-Object { $_.name -like "*.exe" }
    if ($exeAsset) {
        Write-Host "`n✓ Executable found in release: $($exeAsset.name)" -ForegroundColor Green
        Write-Host "  Download URL: $($exeAsset.browser_download_url)" -ForegroundColor Cyan
    } else {
        Write-Host "`n✗ No executable found in release" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "Error testing GitHub API: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "This might be due to:" -ForegroundColor Yellow
    Write-Host "  - Network connectivity issues" -ForegroundColor Yellow
    Write-Host "  - GitHub API rate limiting" -ForegroundColor Yellow
    Write-Host "  - Repository access issues" -ForegroundColor Yellow
}

Write-Host "`nTest completed." -ForegroundColor Green 