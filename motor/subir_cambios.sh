#!/bin/zsh
# Sube a GitHub los cambios del motor (simbolos.json, expertos.json, plantilla.html…).
# Al recibirlos, GitHub Actions regenera la versión web sola (.github/workflows/actualizar.yml).
# Uso: zsh motor/subir_cambios.sh "mensaje opcional"
set -e
cd "${0:A:h}/.."
export PATH="$HOME/.local/bin:$PATH"
git pull -q --rebase origin main
git add motor
if git diff --cached --quiet; then
  echo "Sin cambios en el motor."
  exit 0
fi
git commit -q -m "${1:-Actualiza el motor de la app}"
git push -q origin main
echo "Cambios subidos; GitHub regenera la versión web en uno o dos minutos."
