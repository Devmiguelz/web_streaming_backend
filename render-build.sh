#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "🔧 Instalando dependencias de Python..."
pip install -r requirements.txt

echo "🌐 Instalando Chromium para Playwright..."
playwright install chromium

echo "✅ Build completado exitosamente"