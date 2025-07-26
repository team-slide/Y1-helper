# Git commit and merge script for Y1-helper
# This script will commit changes to both dev and master branches

Write-Host "=== Y1-Helper Git Commit and Merge Script ===" -ForegroundColor Green
Write-Host ""

# Set git user info
Write-Host "Setting git user configuration..." -ForegroundColor Yellow
git config user.name "team-slide"
git config user.email "itsryanspecter@gmail.com"
Write-Host "Git user configured." -ForegroundColor Green
Write-Host ""

# Check current branch
Write-Host "Current branch:" -ForegroundColor Yellow
git branch --show-current
Write-Host ""

# Add all changes
Write-Host "Adding all changes..." -ForegroundColor Yellow
git add -A
Write-Host "Changes added." -ForegroundColor Green
Write-Host ""

# Check what's being committed
Write-Host "Files to be committed:" -ForegroundColor Yellow
git status --porcelain
Write-Host ""

# Commit changes
Write-Host "Committing changes..." -ForegroundColor Yellow
git commit -m "Fix new.xml auto-copy and firmware file management - no XML editing, only file copying with rom/ path preservation"
Write-Host "Changes committed." -ForegroundColor Green
Write-Host ""

# Push to current branch
Write-Host "Pushing to current branch..." -ForegroundColor Yellow
$current_branch = git branch --show-current
git push origin $current_branch
Write-Host "Pushed to $current_branch." -ForegroundColor Green
Write-Host ""

# If we're on dev, merge from master
if ($current_branch -eq "dev") {
    Write-Host "Merging master into dev..." -ForegroundColor Yellow
    git merge master --no-ff -m "Merge master into dev: Include new.xml with updated rom/ paths and fix y1_helper new.xml auto-copy functionality"
    Write-Host "Merge completed." -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Pushing merged dev branch..." -ForegroundColor Yellow
    git push origin dev
    Write-Host "Dev branch pushed." -ForegroundColor Green
    Write-Host ""
}

# If we're on master, switch to dev and merge
if ($current_branch -eq "master") {
    Write-Host "Switching to dev branch..." -ForegroundColor Yellow
    git checkout dev
    Write-Host "Switched to dev." -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Merging master into dev..." -ForegroundColor Yellow
    git merge master --no-ff -m "Merge master into dev: Include new.xml with updated rom/ paths and fix y1_helper new.xml auto-copy functionality"
    Write-Host "Merge completed." -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Pushing dev branch..." -ForegroundColor Yellow
    git push origin dev
    Write-Host "Dev branch pushed." -ForegroundColor Green
    Write-Host ""
}

Write-Host "=== Script completed successfully! ===" -ForegroundColor Green
Write-Host "Both dev and master branches are now updated with new.xml and y1_helper fixes." -ForegroundColor Cyan 