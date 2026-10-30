"""Configure the local app's private Supabase secret key."""
from getpass import getpass
import os
from pathlib import Path

key = getpass("Chave secreta sb_secret_ do Supabase (entrada oculta): ").strip()
if not key.startswith("sb_secret_") or len(key) < 30:
    raise SystemExit("Chave inválida. Copie uma chave secreta sb_secret_ do painel Supabase.")
directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Estrela Concept"
directory.mkdir(parents=True, exist_ok=True)
target = directory / "supabase.secret"
target.write_text(key, encoding="utf-8")
print(f"Chave salva fora da pasta do site: {target}")
print("Reinicie o servidor para ativar o Supabase.")
