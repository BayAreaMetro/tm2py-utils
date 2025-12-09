@echo off
REM Generate summaries and deploy to dashboard
REM This is a convenience wrapper around run_and_deploy_dashboard.py

echo ================================================================================
echo CTRAMP VALIDATION DASHBOARD DEPLOYMENT
echo ================================================================================
echo.

REM Activate conda environment if needed
if defined CONDA_DEFAULT_ENV (
    echo Using conda environment: %CONDA_DEFAULT_ENV%
) else (
    echo Activating tm2py-utils conda environment...
    call conda activate tm2py-utils
)

echo.
echo Choose an option:
echo   1. Generate ALL summaries and copy to dashboard
echo   2. Generate CORE summaries only and copy to dashboard  
echo   3. Generate VALIDATION summaries only and copy to dashboard
echo   4. Copy existing summaries to dashboard (skip generation)
echo   5. Generate summaries and LAUNCH dashboard
echo.

set /p choice="Enter choice (1-5): "

if "%choice%"=="1" (
    echo Running: Generate all summaries...
    python run_and_deploy_dashboard.py --config validation_config.yaml
)

if "%choice%"=="2" (
    echo Running: Generate core summaries only...
    python run_and_deploy_dashboard.py --config validation_config.yaml --summaries core
)

if "%choice%"=="3" (
    echo Running: Generate validation summaries only...
    python run_and_deploy_dashboard.py --config validation_config.yaml --summaries validation
)

if "%choice%"=="4" (
    echo Running: Copy existing summaries...
    python run_and_deploy_dashboard.py --config validation_config.yaml --skip-generation
)

if "%choice%"=="5" (
    echo Running: Generate all summaries and launch dashboard...
    python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard --port 8503
)

echo.
echo ================================================================================
echo Done!
echo ================================================================================
pause
