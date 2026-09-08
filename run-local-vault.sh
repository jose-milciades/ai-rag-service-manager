# Arranca el servicio leyendo configuracion desde Vault local, en vez de
# .env (ver get_settings(), pendientes.md P-17). NO commitear -- contiene un
# VAULT_TOKEN real (ver .gitignore: run-local-vault.sh esta excluido).

export VAULT_ADDR=http://localhost:8200/
export USE_VAULT_CONFIG=true
VAULT_TOKEN="${VAULT_TOKEN}"

exec uv run python -m app.main
