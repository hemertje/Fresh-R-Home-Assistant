@echo off
REM ========================================
REM Fresh-R Deployment Script (Testing Phase)
REM Automatically cleans cache and deploys
REM ========================================

echo.
echo ========================================
echo Fresh-R Deployment to Home Assistant
echo ========================================
echo.

REM Step 1: Delete Python cache
echo [1/4] Cleaning Python cache...
powershell -Command "Remove-Item -Recurse -Force '\\192.168.2.5\config\custom_components\fresh_r\__pycache__' -ErrorAction SilentlyContinue"
echo       Cache cleaned!
echo.

REM Step 2: Copy all Python files
echo [2/4] Copying Python files...
copy /Y custom_components\fresh_r\*.py \\192.168.2.5\config\custom_components\fresh_r\
echo       Python files copied!
echo.

REM Step 3: Copy manifest and strings
echo [3/4] Copying manifest and strings...
copy /Y custom_components\fresh_r\manifest.json \\192.168.2.5\config\custom_components\fresh_r\
copy /Y custom_components\fresh_r\strings.json \\192.168.2.5\config\custom_components\fresh_r\
echo       Config files copied!
echo.

REM Step 4: Copy translations
echo [4/4] Copying translations...
copy /Y custom_components\fresh_r\translations\*.json \\192.168.2.5\config\custom_components\fresh_r\translations\
echo       Translations copied!
echo.

echo ========================================
echo Deployment Complete!
echo ========================================
echo.
echo NEXT STEPS:
echo 1. Restart Home Assistant
echo 2. Wait for HA to come online
echo 3. Install/Configure Fresh-R integration
echo.
echo Press any key to exit...
pause >nul
