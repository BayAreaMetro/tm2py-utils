# CityPhi Environment Setup Script
# This script helps set up a Python environment for the CityPhi visualization notebook

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CityPhi Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (Test-Path ".\venv") {
    Write-Host "Virtual environment 'venv' already exists." -ForegroundColor Yellow
    $createNew = Read-Host "Do you want to recreate it? (y/N)"
    if ($createNew -eq 'y' -or $createNew -eq 'Y') {
        Write-Host "Removing existing environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force .\venv
    } else {
        Write-Host "Using existing environment." -ForegroundColor Green
        Write-Host ""
        Write-Host "To activate: .\venv\Scripts\Activate.ps1" -ForegroundColor Green
        exit 0
    }
}

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create virtual environment!" -ForegroundColor Red
    Write-Host "Make sure Python 3.11+ is installed and in your PATH." -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# Install requirements
Write-Host "Installing Python packages from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install requirements!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Base packages installed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Prompt for CityPhi installation
Write-Host "IMPORTANT: CityPhi must be installed from your EMME installation." -ForegroundColor Yellow
Write-Host ""
Write-Host "Common EMME paths:" -ForegroundColor Cyan
Write-Host "  - C:\Program Files\INRO\Emme\Emme 4.6.2\Python312-64\Lib\site-packages\" -ForegroundColor Gray
Write-Host "  - C:\Program Files\INRO\Emme\Emme 4.6.1\Python311-64\Lib\site-packages\" -ForegroundColor Gray
Write-Host ""

$emmePath = Read-Host "Enter path to EMME site-packages (or press Enter to skip)"

if ($emmePath -and (Test-Path $emmePath)) {
    Write-Host "Installing CityPhi packages from EMME..." -ForegroundColor Cyan
    
    $cityPhiPackages = Get-ChildItem -Path $emmePath -Filter "cityphi_*.whl"
    
    if ($cityPhiPackages.Count -gt 0) {
        foreach ($package in $cityPhiPackages) {
            Write-Host "Installing $($package.Name)..." -ForegroundColor Gray
            pip install $package.FullName
        }
        Write-Host "CityPhi packages installed!" -ForegroundColor Green
    } else {
        Write-Host "No CityPhi wheel files found in specified path." -ForegroundColor Yellow
        Write-Host "You'll need to install CityPhi manually." -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping CityPhi installation." -ForegroundColor Yellow
    Write-Host "Install manually with:" -ForegroundColor Yellow
    Write-Host '  pip install "C:\Path\To\EMME\site-packages\cityphi_*.whl"' -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Ensure CityPhi is installed (if you skipped it above)" -ForegroundColor White
Write-Host "2. Place your data in the data/ folder (see data/README.md)" -ForegroundColor White
Write-Host "3. Launch Jupyter: jupyter notebook notebooks/MTC_CityPhi_Tutorial.ipynb" -ForegroundColor White
Write-Host "4. Select the 'venv' kernel in the notebook" -ForegroundColor White
Write-Host ""
Write-Host "Environment is activated. To deactivate: deactivate" -ForegroundColor Gray
