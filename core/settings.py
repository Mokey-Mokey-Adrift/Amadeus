import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"
SUPPORTED_LANGUAGES = {"ru", "en"}


def load_settings():
    if not SETTINGS_FILE.exists():
        return {"language": "ru"}

    with SETTINGS_FILE.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    language = settings.get("language", "ru")
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported application language in {SETTINGS_FILE}: {language}")
    return {"language": language}


def set_language(language):
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")

    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = SETTINGS_FILE.with_suffix(".json.tmp")
    with temporary_file.open("w", encoding="utf-8") as settings_file:
        json.dump({"language": language}, settings_file, ensure_ascii=False, indent=2)
    temporary_file.replace(SETTINGS_FILE)
    return {"language": language}
