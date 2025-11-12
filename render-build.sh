#!/usr/bin/env bash
# Exit on error
set -o errexit

# Instalar dependencias de Python
pip install -r requirements.txt

# Instalar navegador Chromium para Playwright
playwright install chromium

# Instalar dependencias del sistema
playwright install-deps chromium