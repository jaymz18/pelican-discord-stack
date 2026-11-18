"""Validiert die Pelican-Eggs im Ordner eggs/ (Struktur, Variablen, Startbefehl)."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_KEYS = {"meta", "name", "author", "description", "docker_images", "startup", "config", "scripts", "variables"}
VAR_KEYS = {"name", "description", "env_variable", "default_value", "user_viewable", "user_editable", "rules", "field_type"}

errors: list[str] = []


def err(egg: str, msg: str) -> None:
    errors.append(f"{egg}: {msg}")


for path in sorted((ROOT / "eggs").glob("*.json")):
    name = path.name
    try:
        egg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(name, f"ungültiges JSON: {exc}")
        continue

    missing = REQUIRED_KEYS - egg.keys()
    if missing:
        err(name, f"fehlende Schlüssel: {sorted(missing)}")
        continue

    if egg["meta"].get("version") not in {"PTDL_v2", "PLCN_v1"}:
        err(name, "meta.version muss PTDL_v2 oder PLCN_v1 sein")
    if not egg["meta"].get("update_url", "").endswith(name):
        err(name, "meta.update_url zeigt nicht auf diese Datei")
    if not egg["docker_images"]:
        err(name, "keine docker_images definiert")
    for img in egg["docker_images"].values():
        if img != img.lower():
            err(name, f"Image-Name muss lowercase sein: {img}")

    for key in ("files", "startup", "logs"):
        try:
            json.loads(egg["config"][key])
        except (KeyError, json.JSONDecodeError):
            err(name, f"config.{key} ist kein gültiger JSON-String")

    install = egg["scripts"].get("installation", {})
    if not install.get("script") or not install.get("container"):
        err(name, "Installationsskript oder -container fehlt")

    env_names = set()
    for var in egg["variables"]:
        missing_v = VAR_KEYS - var.keys()
        if missing_v:
            err(name, f"Variable {var.get('env_variable')} fehlt {sorted(missing_v)}")
        env = var.get("env_variable", "")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", env):
            err(name, f"ungültiger Variablenname: {env}")
        if env in env_names:
            err(name, f"doppelte Variable: {env}")
        env_names.add(env)

    for placeholder in re.findall(r"{{(\w+)}}", egg["startup"]):
        if placeholder not in env_names and not placeholder.startswith("SERVER_"):
            err(name, f"Startbefehl nutzt unbekannte Variable {{{{{placeholder}}}}}")

    print(f"geprüft: {name} ({len(env_names)} Variablen)")

if errors:
    print("\n".join(f"FEHLER {e}" for e in errors))
    sys.exit(1)
print("Alle Eggs sind gültig.")
