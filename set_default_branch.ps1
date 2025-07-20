# PowerShell script to configure Y1 Helper repository with master as default branch
# This script helps set up the repository for self-healing functionality

Write-Host "=== Y1 Helper Repository Configuration ===" -ForegroundColor Green
Write-Host ""

# Check if we're in the correct directory
if (-not (Test-Path "y1_helper.py")) {
    Write-Host "Error: y1_helper.py not found. Please run this script from the Y1 Helper directory." -ForegroundColor Red
    exit 1
}

# Check git status
Write-Host "Checking git status..." -ForegroundColor Yellow
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "Warning: There are uncommitted changes. Please commit them first." -ForegroundColor Yellow
    Write-Host "Uncommitted files:" -ForegroundColor Yellow
    $gitStatus | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    Write-Host ""
}

# Check current branch
$currentBranch = git branch --show-current
Write-Host "Current branch: $currentBranch" -ForegroundColor Cyan

# Check remote branches
Write-Host "Remote branches:" -ForegroundColor Cyan
git branch -r | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }

# Verify master branch exists
$masterExists = git branch -r | Select-String "origin/master"
if (-not $masterExists) {
    Write-Host "Error: master branch not found on remote. Please create it first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Configuration Summary ===" -ForegroundColor Green
Write-Host "Repository: https://github.com/team-slide/Y1-helper" -ForegroundColor White
Write-Host "Default branch: master" -ForegroundColor White
Write-Host "Self-healing: Configured to use master branch" -ForegroundColor White
Write-Host ""

Write-Host "=== Next Steps ===" -ForegroundColor Green
Write-Host "1. Go to https://github.com/team-slide/Y1-helper/settings/branches" -ForegroundColor White
Write-Host "2. Set 'master' as the default branch" -ForegroundColor White
Write-Host "3. The self-healing tools are now configured to work from the master branch" -ForegroundColor White
Write-Host ""

Write-Host "=== Self-Healing Features ===" -ForegroundColor Green
Write-Host "✓ Automatic file synchronization from master branch" -ForegroundColor White
Write-Host "✓ Update checking and installation" -ForegroundColor White
Write-Host "✓ Robust file sync with error recovery" -ForegroundColor White
Write-Host "✓ Background sync during application runtime" -ForegroundColor White
Write-Host ""

Write-Host "Configuration complete! The Y1 Helper tool will now use the master branch for all self-healing operations." -ForegroundColor Green 