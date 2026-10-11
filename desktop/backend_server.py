"""JSON-lines bridge between the Electron renderer and the Python app core."""

import json
import os
import queue
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from core import agent, chat_manager, settings, tools, voice

MESSAGE_PREFIX = "@@AMADEUS@@"
OUTPUT_LOCK = threading.Lock()
VOICE_MESSAGES = queue.Queue()
VOICE_ACTIVE = threading.Event()
AI_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="amadeus-ai")


def emit(message):
    with OUTPUT_LOCK:
        sys.stdout.write(MESSAGE_PREFIX + json.dumps(message, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def emit_state():
    emit({"type": "event", "event": "state", "state": chat_manager.load_chats()})


def run_prompt(chat_id, text, history, language="ru"):
    try:
        result = agent.ask_ai(text, history, language)
        if result["type"] == "function":
            function_name = result["name"]
            arguments = result["args"]
            if function_name == "set_alarm":
                hour = arguments.get("hour", 0)
                minute = arguments.get("minute", 0)
                tools.set_alarm(hour, minute, lambda _message: None)
                tool_result = (
                    f"Alarm set for {hour:02d}:{minute:02d}."
                    if language == "en"
                    else f"Будильник поставлен на {hour}:{minute}."
                )
            elif function_name == "get_weather":
                tool_result = tools.get_weather(arguments.get("city"), language)
            elif function_name == "get_current_time":
                tool_result = tools.get_current_time(language)
            elif function_name == "web_search":
                tool_result = tools.web_search(arguments.get("query", ""))
            else:
                raise ValueError(f"Unsupported assistant function: {function_name}")

            history_with_prompt = [*history, {"role": "user", "content": text}]
            answer = agent.finalize_tool_response(
                result["tool_call_id"],
                tool_result or (
                    "Could not retrieve a result."
                    if language == "en"
                    else "Не удалось получить результат."
                ),
                history_with_prompt,
                language,
            )
        else:
            answer = result["content"]

        chat_manager.add_message_to_chat(chat_id, "assistant", answer)
        emit_state()
    except Exception as error:
        emit({"type": "event", "event": "error", "message": str(error)})
    finally:
        emit({"type": "event", "event": "processing", "active": False})


def run_voice_loop():
    try:
        language = settings.load_settings()["language"]
        greeting = (
            "Hello! I'm Amadeus. Say my name to get my attention."
            if language == "en"
            else "Привет! Я Амадэус. Позовите меня по имени."
        )
        listen_prompt = "I'm listening." if language == "en" else "Слушаю вас."
        voice.amadeus_say(greeting, None)
        while VOICE_ACTIVE.is_set():
            voice.wait_for_wake_word()
            if not VOICE_ACTIVE.is_set():
                break
            text = voice.amadeus_listen(
                say_first=listen_prompt,
                timeout_seconds=15,
                say_callback=voice.amadeus_say,
            ).strip()
            if not text:
                continue

            state = chat_manager.load_chats()
            active_chat_id = state["active_chat_id"]
            history = chat_manager.get_active_chat_messages()
            chat_manager.add_message_to_chat(active_chat_id, "user", text)
            emit_state()
            emit({"type": "event", "event": "processing", "active": True})
            language = settings.load_settings()["language"]
            AI_EXECUTOR.submit(run_prompt, active_chat_id, text, history, language)
    except Exception as error:
        language = settings.load_settings()["language"]
        prefix = "Voice mode" if language == "en" else "Голосовой режим"
        emit({"type": "event", "event": "error", "message": f"{prefix}: {error}"})
    finally:
        VOICE_ACTIVE.clear()
        emit({"type": "event", "event": "voice", "active": False})


def handle_command(command):
    action = command.get("action")
    payload = command.get("payload") or {}

    if action == "get_state":
        return chat_manager.load_chats()
    if action == "get_settings":
        return settings.load_settings()
    if action == "set_language":
        result = settings.set_language(payload["language"])
        emit({"type": "event", "event": "settings", "settings": result})
        return result
    if action == "activate_mode":
        chat_mode = payload["mode"]
        chat_manager.activate_chat_mode(chat_mode, settings.load_settings()["language"])
        emit_state()
        return {"ok": True}
    if action == "create_chat":
        chat_manager.create_new_chat(
            payload.get("mode", "assistant"),
            settings.load_settings()["language"],
        )
        emit_state()
        return {"ok": True}
    if action == "switch_chat":
        chat_manager.switch_chat(payload["chat_id"])
        emit_state()
        return {"ok": True}
    if action == "delete_chat":
        chat_manager.delete_chat(payload["chat_id"], settings.load_settings()["language"])
        emit_state()
        return {"ok": True}
    if action == "rename_chat":
        title = payload["title"].strip()
        if not title:
            language = settings.load_settings()["language"]
            message = "Chat title cannot be empty." if language == "en" else "Название чата не может быть пустым."
            raise ValueError(message)
        chat_manager.rename_chat(payload["chat_id"], title)
        emit_state()
        return {"ok": True}
    if action == "send_message":
        text = payload["text"].strip()
        if not text:
            language = settings.load_settings()["language"]
            message = "Message cannot be empty." if language == "en" else "Сообщение не может быть пустым."
            raise ValueError(message)
        state = chat_manager.load_chats()
        chat_id = state["active_chat_id"]
        history = chat_manager.get_active_chat_messages()
        chat_manager.add_message_to_chat(chat_id, "user", text)
        emit_state()
        emit({"type": "event", "event": "processing", "active": True})
        language = settings.load_settings()["language"]
        AI_EXECUTOR.submit(run_prompt, chat_id, text, history, language)
        return {"ok": True}
    if action == "toggle_voice":
        if VOICE_ACTIVE.is_set():
            VOICE_ACTIVE.clear()
            emit({"type": "event", "event": "voice", "active": False})
        else:
            VOICE_ACTIVE.set()
            threading.Thread(target=run_voice_loop, daemon=True).start()
            emit({"type": "event", "event": "voice", "active": True})
        return {"active": VOICE_ACTIVE.is_set()}
    raise ValueError(f"Unknown action: {action}")


def main():
    tools_thread = threading.Thread(
        target=tools.alarm_watcher,
        args=(lambda message: voice.amadeus_say(message, VOICE_MESSAGES),),
        daemon=True,
    )
    tools_thread.start()

    def forward_voice_messages():
        while True:
            sender, text = VOICE_MESSAGES.get()
            if sender == "Амадэус":
                state = chat_manager.load_chats()
                chat_id = state["active_chat_id"]
                chat_manager.add_message_to_chat(chat_id, "assistant", text)
                emit_state()

    threading.Thread(target=forward_voice_messages, daemon=True).start()
    emit_state()

    for line in sys.stdin:
        try:
            command = json.loads(line)
            request_id = command.get("request_id")
            try:
                result = handle_command(command)
                emit({
                    "type": "response",
                    "request_id": request_id,
                    "ok": True,
                    "result": result,
                })
            except Exception as error:
                emit({
                    "type": "response",
                    "request_id": request_id,
                    "ok": False,
                    "error": str(error),
                })
        except json.JSONDecodeError as error:
            emit({"type": "event", "event": "error", "message": f"Bad request: {error}"})

    VOICE_ACTIVE.clear()
    AI_EXECUTOR.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
