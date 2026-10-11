# core/chat_manager.py
import json
import os
import uuid
from datetime import datetime

CHATS_FILE = "data/chats.json"
CHAT_MODES = {"assistant", "kurisu"}


def _ensure_data_dir():
    if not os.path.exists("data"):
        os.makedirs("data")


def _new_chat(chat_mode, language="ru"):
    return {
        "id": str(uuid.uuid4()),
        "title": (
            ("New chat with Kurisu" if language == "en" else "Новый чат с Курису")
            if chat_mode == "kurisu"
            else ("New chat" if language == "en" else "Новый чат")
        ),
        "messages": [],
        "mode": chat_mode,
    }


def _set_active_chat(data, chat):
    chat_mode = chat.get("mode", "assistant")
    active_chat_ids = data.setdefault("active_chat_ids", {})
    active_chat_ids[chat_mode] = chat["id"]
    data["active_chat_id"] = chat["id"]


def load_chats():
    _ensure_data_dir()
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        chat = _new_chat("assistant")
        data = {
            "active_chat_id": chat["id"],
            "active_chat_ids": {"assistant": chat["id"]},
            "chats": [chat],
        }

    changed = False
    for chat in data["chats"]:
        if "mode" not in chat:
            chat["mode"] = "assistant"
            changed = True
    if "active_chat_ids" not in data:
        data["active_chat_ids"] = {}
        changed = True
    for chat_mode in CHAT_MODES:
        active_id = data["active_chat_ids"].get(chat_mode)
        if not any(
            chat["id"] == active_id and chat.get("mode") == chat_mode
            for chat in data["chats"]
        ):
            replacement = next(
                (chat for chat in data["chats"] if chat.get("mode") == chat_mode),
                None,
            )
            if replacement:
                data["active_chat_ids"][chat_mode] = replacement["id"]
                changed = True
    if changed:
        save_chats(data)
    return data

def save_chats(data):
    _ensure_data_dir()
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create_new_chat(chat_mode="assistant", language="ru"):
    if chat_mode not in CHAT_MODES:
        raise ValueError(f"Unknown chat mode: {chat_mode}")
    data = load_chats()
    chat = _new_chat(chat_mode, language)
    data["chats"].append(chat)
    _set_active_chat(data, chat)
    save_chats(data)
    return chat["id"]


def activate_chat_mode(chat_mode, language="ru"):
    if chat_mode not in CHAT_MODES:
        raise ValueError(f"Unknown chat mode: {chat_mode}")
    data = load_chats()
    active_id = data["active_chat_ids"].get(chat_mode)
    chat = next(
        (
            item for item in data["chats"]
            if item["id"] == active_id and item.get("mode") == chat_mode
        ),
        None,
    )
    if chat is None:
        chat = _new_chat(chat_mode, language)
        data["chats"].append(chat)
    _set_active_chat(data, chat)
    save_chats(data)
    return chat["id"]

def delete_chat(chat_id, language="ru"):
    data = load_chats()
    deleted = next((chat for chat in data["chats"] if chat["id"] == chat_id), None)
    if deleted is None:
        return
    chat_mode = deleted.get("mode", "assistant")
    data["chats"] = [c for c in data["chats"] if c["id"] != chat_id]
    replacement = next(
        (chat for chat in data["chats"] if chat.get("mode") == chat_mode),
        None,
    )
    if replacement is None:
        replacement = _new_chat(chat_mode, language)
        data["chats"].append(replacement)
    active_mode_chat_id = data["active_chat_ids"].get(chat_mode)
    if (
        active_mode_chat_id == chat_id
        or data["active_chat_id"] == chat_id
        or not any(
            chat["id"] == active_mode_chat_id and chat.get("mode") == chat_mode
            for chat in data["chats"]
        )
    ):
        _set_active_chat(data, replacement)
    save_chats(data)

def rename_chat(chat_id, new_title):
    data = load_chats()
    for chat in data["chats"]:
        if chat["id"] == chat_id:
            chat["title"] = new_title
            break
    save_chats(data)

def add_message_to_active_chat(role, content):
    data = load_chats()
    add_message_to_chat(data["active_chat_id"], role, content)

def add_message_to_chat(chat_id, role, content):
    data = load_chats()
    chat = next((item for item in data["chats"] if item["id"] == chat_id), None)
    if chat is None:
        raise ValueError(f"Chat not found: {chat_id}")

    chat["messages"].append({
        "role": role,
        "content": content,
        "time": datetime.now().isoformat(),
    })

    # Автопереименование: первое сообщение пользователя становится заголовком.
    default_titles = (
        {"Новый чат с Курису", "New chat with Kurisu"}
        if chat.get("mode") == "kurisu"
        else {"Новый чат", "New chat"}
    )
    if role == "user" and chat["title"] in default_titles and content:
        chat["title"] = content[:30] + ("..." if len(content) > 30 else "")

    save_chats(data)

def get_active_chat_messages():
    data = load_chats()
    active_chat = next((c for c in data["chats"] if c["id"] == data["active_chat_id"]), None)
    return active_chat["messages"] if active_chat else []

def switch_chat(chat_id):
    data = load_chats()
    chat = next((item for item in data["chats"] if item["id"] == chat_id), None)
    if chat is None:
        raise ValueError(f"Chat not found: {chat_id}")
    _set_active_chat(data, chat)
    save_chats(data)