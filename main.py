import flet as ft
import threading
import queue
from core import tools, voice

# Глобальная очередь для безопасной передачи сообщений в UI
message_queue = queue.Queue()

def main(page: ft.Page):
    print("🚀 Запуск Амадэуса v3.0 (Flet 1.0)...")
    
    def say_callback(text):
        voice.amadeus_say(text, message_queue)

    # 1. Запускаем сторожа будильников в фоне
    threading.Thread(target=tools.alarm_watcher, args=(say_callback,), daemon=True).start()
    print("✅ Сторож будильников запущен")
    
    # 2. Создаём и инициализируем UI
    from ui.interface import AmadeusUI
    app = AmadeusUI(page, message_queue)
    print("✅ Интерфейс запущен. Жду команд...")

if __name__ == "__main__":
    ft.run(main)