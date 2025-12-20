@echo off
REM Build script for Windows
echo Building Claude Agent Manager...
python build.py %*
if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful! Executable is in dist\
) else (
    echo.
    echo Build failed!
)
pause
