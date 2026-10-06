# core/chat_manager.py
import json
import os
import uuid
from datetime import datetime

CHATS_FILE = "data/chats.json"

def _ensure_data_dir():
    if not os.path.exists("data"):
        os.makedirs("data")

def load_chats():
    _ensure_data_dir()
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Дефолтное состояние: один пустой чат
    default_chat_id = str(uuid.uuid4())
    return {
        "active_chat_id": default_chat_id,
        "chats": [
            {"id": default_chat_id, "title": "Новый чат", "messages": []}
        ]
    }

def save_chats(data):
    _ensure_data_dir()
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create_new_chat():
    data = load_chats()
    new_id = str(uuid.uuid4())
    data["chats"].append({"id": new_id, "title": "Новый чат", "messages": []})
    data["active_chat_id"] = new_id
    save_chats(data)
    return new_id

def delete_chat(chat_id):
    data = load_chats()
    data["chats"] = [c for c in data["chats"] if c["id"] != chat_id]
    
    # Если удалили активный чат
    if data["active_chat_id"] == chat_id:
        if data["chats"]:
            # Есть другие чаты — переключаемся на первый
            data["active_chat_id"] = data["chats"][0]["id"]
            save_chats(data)  # Сначала сохраняем удаление
        else:
            # Список пуст — создаём новый чат с нуля
            new_id = str(uuid.uuid4())
            data["chats"] = [{"id": new_id, "title": "Новый чат", "messages": []}]
            data["active_chat_id"] = new_id
            save_chats(data)
    else:
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
    active_chat = next((c for c in data["chats"] if c["id"] == data["active_chat_id"]), None)
    if active_chat:
        active_chat["messages"].append({"role": role, "content": content, "time": datetime.now().isoformat()})
        
        # Автопереименование: если это первое сообщение пользователя, делаем его заголовком
        if role == "user" and active_chat["title"] == "Новый чат" and len(content) > 0:
            active_chat["title"] = content[:30] + ("..." if len(content) > 30 else "")
            
        save_chats(data)

def get_active_chat_messages():
    data = load_chats()
    active_chat = next((c for c in data["chats"] if c["id"] == data["active_chat_id"]), None)
    return active_chat["messages"] if active_chat else []

def switch_chat(chat_id):
    data = load_chats()
    data["active_chat_id"] = chat_id
    save_chats(data)