@echo off
REM Windows launcher for the StepFun image CLI.
REM Resolves the package directory from this script's location, so it works
REM no matter what the current working directory is.
setlocal
set "HERE=%~dp0"
python -m stepfun_image.cli %*
endlocal
