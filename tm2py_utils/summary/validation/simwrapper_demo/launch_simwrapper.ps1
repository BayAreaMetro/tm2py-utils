# PowerShell script to launch SimWrapper with correct conda environment
# Save as launch_simwrapper.ps1 and run from PowerShell

Write-Host "Activating tm2py-utils conda environment..." -ForegroundColor Green

# Activate conda environment
& conda activate tm2py-utils

Write-Host "Launching SimWrapper..." -ForegroundColor Green

# Launch SimWrapper
& simwrapper open .

Write-Host "SimWrapper should now be opening in your browser..." -ForegroundColor Yellow