::
:: batch file to run maz_taz_checker interatively in a semi-automated way
::

setlocal enabledelayedexpansion

set WORKSPACE=E:\TM2_maz_taz_v2.2
set MAZ_TAZ_DIR=E:\GitHub\tm2py-utils\tm2py_utils\inputs\maz_taz
set NUM_ITERS=5

:: run this in WORKSPACE
:: Note that maz_taz_checker.py uses arcpy so use an arcpy conda environment

:: copy initial Files
copy %MAZ_TAZ_DIR%\Readme.md .
copy %MAZ_TAZ_DIR%\blocks_mazs_tazs_v2.1.1.csv .

:: loop
for /L %%V in (1,1,%NUM_ITERS%) do (

  set /a NEXTV=%%V+1
  echo 2.1.%%V 2.1.!NEXTV!

  copy blocks_mazs_tazs_v2.1.%%V.csv blocks_mazs_tazs.csv

  call Rscript.exe --vanilla "%MAZ_TAZ_DIR%\csv_to_dbf.R"
  IF ERRORLEVEL 1 goto error

  rem save the dbf for this version
  copy blocks_mazs_tazs.dbf blocks_mazs_tazs_v2.1.%%V.dbf

  if not %%V==%NUM_ITERS% python "%MAZ_TAZ_DIR%\maz_taz_checker.py"
  if %%V==%NUM_ITERS% python "%MAZ_TAZ_DIR%\maz_taz_checker.py" --dissolve
  IF ERRORLEVEL 1 goto error

  if not %%V==%NUM_ITERS% (
    copy maz_taz_checker.log maz_taz_checker_v2.1.!NEXTV!.log
    copy blocks_mazs_tazs_updated.csv blocks_mazs_tazs_v2.1.!NEXTV!.csv
  )
)

echo Success!
goto done

:error
echo Oh no, an error

:done
echo Done