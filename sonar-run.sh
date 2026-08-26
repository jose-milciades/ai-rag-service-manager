#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${SONAR_TOKEN:-}" ]]; then
  echo "SONAR_TOKEN no está configurado." >&2
  exit 1
fi

# Genera coverage.xml para que sonar-scanner lo suba (sonar.python.coverage.reportPaths).
# No bloquea el analisis si algun test falla: igual se sube lo que se pudo cubrir.
.venv/bin/python -m pytest tests --continue-on-collection-errors -q --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml || true

sonar-scanner -Dsonar.token="$SONAR_TOKEN" -X
