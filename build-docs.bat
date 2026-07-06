@echo off
REM Build script for local documentation development (Windows)

echo.
echo Building cash-optimizer documentation...
echo.

REM Check if mkdocs is installed
python -m pip show mkdocs >nul 2>&1
if errorlevel 1 (
    echo mkdocs not found. Installing dependencies...
    pip install -r docs-requirements.txt
)

REM Build documentation
echo Building with MkDocs...
python -m mkdocs build -f zensical.yaml -d docs/build

echo.
echo Build complete!
echo.
echo Output directory: docs\build
echo.
echo To serve locally:
echo   mkdocs serve -f zensical.yaml
echo.
echo Open in browser at: http://localhost:8000
echo.
