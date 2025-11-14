@echo off
REM SimWrapper Launch Script for tm2py-utils
REM This script ensures the correct conda environment is activated before launching SimWrapper

echo Activating tm2py-utils environment...
call conda activate tm2py-utils

echo Launching SimWrapper...
simwrapper open .

pause