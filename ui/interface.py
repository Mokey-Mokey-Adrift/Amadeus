import flet as ft
import threading
import queue
import asyncio
from core import voice, agent, tools

# Цвета в стиле Steins;Gate
COLOR_BG = "#1a1a1a"
COLOR_SURFACE = "#2d2d2d"
COLOR_ACCENT = "#ff6600"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#aaaaaa"
COLOR_USER = "#4da6ff"
COLOR_AMADEUS = "#00ff00"


class AmadeusUI:
    def __init__(self, page: ft.Page, message_queue: queue.Queue):
        self.page = page
        self.message_queue = message_queue
        self.is_running = False
        self.is_processing = False  # <-- НОВОЕ: флаг обработки
        
        # Настройка страницы
        page.title = "Amadeus v3.0"
        page.bgcolor = COLOR_BG
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window_min_width = 500
        page.window_min_height = 600
        
        # Элементы UI
        self.chat_column = ft.Column(
            expand=True,
            spacing=10,
            scroll=ft.ScrollMode.AUTO
        )
        
        self.input_field = ft.TextField(
            hint_text="Введите команду...",
            expand=True,
            border_radius=10,
            bgcolor=COLOR_SURFACE,
            color=COLOR_TEXT,
            text_size=14,
            on_submit=self.handle_manual_input
        )
        
        # Кнопка отправки (обычное состояние)
        self.send_btn = ft.IconButton(
            icon=ft.Icons.SEND,
            icon_color=COLOR_ACCENT,
            on_click=self.handle_manual_input,
            icon_size=20  # <-- Добавь это
        )
        
        # Индикатор загрузки (состояние "думаю")
        self.loading_indicator = ft.ProgressRing(
            width=15,
            height=15,
            stroke_width=2,
            color=COLOR_ACCENT
        )
        
        # Контейнер для кнопки/индикатора - меняем content вместо visible
        self.send_container = ft.Container(
            content=self.send_btn,
            width=36,
            height=36
        )
        
        self.voice_btn = ft.Button(
            content=ft.Text("▶ Запустить голосовой режим", color=COLOR_TEXT, weight="bold"),
            icon=ft.Icons.MIC,
            bgcolor=COLOR_ACCENT,
            on_click=self.toggle_voice,
            width=200  # Просто width, без min_width и height
        )
        
        self.clear_btn = ft.Button(
            content=ft.Text("Очистить историю", color=COLOR_TEXT_DIM),
            icon=ft.Icons.DELETE,
            on_click=self.clear_history,
            bgcolor="transparent"
        )
        
        # Сборка интерфейса (убраны status_text и typing_indicator)
        page.controls = [
            ft.Text("AMADEUS", size=32, weight="bold", color=COLOR_ACCENT, text_align=ft.TextAlign.CENTER),
            ft.Divider(height=1, color=COLOR_ACCENT),
            self.chat_column,
            ft.Row([self.input_field, self.send_container], spacing=10),
            ft.Row([self.voice_btn, self.clear_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
        ]
        
        # Запуск проверки очереди
        self.page.run_task(self._start_queue_checker)

    def show_loading(self):
        """Показывает индикатор загрузки вместо кнопки отправки"""
        self.is_processing = True
        self.send_container.content = self.loading_indicator  # Меняем содержимое
        self.page.update()
    
    def hide_loading(self):
        """Возвращает кнопку отправки"""
        self.is_processing = False
        self.send_container.content = self.send_btn  # Возвращаем кнопку
        self.page.update()

    async def _start_queue_checker(self):
        """Запускает проверку очереди при старте"""
        import asyncio
        await asyncio.sleep(0.5)  # Ждём инициализации UI
        self.check_queue()

    
    def check_queue(self):
        """Проверяет очередь сообщений (вызывается каждые 100мс)"""
        try:
            while True:
                sender, text = self.message_queue.get_nowait()
                print(f"[DEBUG] Получено из очереди: {sender} -> {text[:50]}...")
                self.add_message(sender, text)
        except queue.Empty:
            pass
        
        # Планируем следующую проверку через 100мс
        self.page.run_task(self._schedule_queue_check)
    
    async def _schedule_queue_check(self):
        """Планирует следующую проверку очереди"""
        import asyncio
        await asyncio.sleep(0.1)
        self.check_queue()

    def clear_history(self, e):
        agent.clear_history()
        self.chat_column.controls.clear()
        print(f"[DEBUG] История очищена. Сообщений: {len(self.chat_column.controls)}")
        self.page.update()
        self.add_message("Система", "История диалога очищена")
    
    def add_message(self, sender, text):
        print(f"[DEBUG] Добавляем в UI: {sender} -> {text[:50]}...")
        
        color = COLOR_USER if sender == "Вы" else COLOR_AMADEUS
        
        msg = ft.Row(
            controls=[
                ft.Text(f"{sender}:", color=color, weight="bold", size=13),
                ft.Text(text, color=COLOR_TEXT, size=13, selectable=True, expand=True)
            ],
            spacing=5
        )
        
        self.chat_column.controls.append(msg)
        print(f"[DEBUG] Всего сообщений в UI: {len(self.chat_column.controls)}")
        
        # Принудительное обновление UI
        self.page.update()
    
    async def _scroll_to_bottom(self):
        self.page.update()
    
    def toggle_voice(self, e):
        if not self.is_running:
            self.is_running = True
            self.voice_btn.content.value = "⏹ Остановить"
            self.voice_btn.icon = ft.Icons.STOP
            self.page.run_task(self._update_ui)
            threading.Thread(target=self.run_voice_loop, daemon=True).start()
        else:
            self.is_running = False
            self.voice_btn.content.value = "▶ Запустить голосовой режим"
            self.voice_btn.icon = ft.Icons.MIC
            self.page.run_task(self._update_ui)
    
    async def _update_ui(self):
        self.page.update()
    
    def run_voice_loop(self):
        voice.amadeus_say("Привет! Я Амадэус. Позовите меня по имени.", self.message_queue)
        while self.is_running:
            voice.wait_for_wake_word()
            if not self.is_running:
                break

            text = voice.amadeus_listen(say_first="Слушаю вас.", timeout_seconds=15, say_callback=voice.amadeus_say)
            
            if text.strip():
                self.add_message("Вы", text)
                
                result = self.handle_command(text)
                if result == "ai":
                    follow = voice.amadeus_listen(say_first="Что-то ещё?", timeout_seconds=15, say_callback=voice.amadeus_say)
                    if follow.strip() and self.is_running:
                        self.add_message("Вы", follow)
                        self.handle_command(follow)
    
    
    def handle_command(self, text):
        if not text.strip():
            self.hide_loading()
            return None
        
        result = agent.ask_ai(text)
        
        if result["type"] == "function":
            func_name = result["name"]
            args = result["args"]
            tool_id = result["tool_call_id"]
            print(f"🛠️ Выполняем функцию: {func_name} с аргументами {args}")
            
            if func_name == "set_alarm":
                h, m = args.get("hour", 0), args.get("minute", 0)
                result_text = f"Будильник поставлен на {h}:{m}."
                tools.set_alarm(h, m, lambda msg: None)
            elif func_name == "get_weather":
                city = args.get("city", None)
                weather_text = tools.get_weather(city)
                result_text = weather_text if weather_text else "Не удалось узнать погоду."
            elif func_name == "get_current_time":
                result_text = tools.get_current_time()
            elif func_name == "web_search":
                search_text = tools.web_search(args.get("query", ""))
                result_text = search_text if search_text else "Ничего не нашёл."
            
            # ✅ ПРАВИЛЬНЫЙ ВЫЗОВ: finalize_tool_response сам записывает результат и возвращает ответ
            final_answer = agent.finalize_tool_response(tool_id, result_text)
            voice.amadeus_say(final_answer, self.message_queue)
        else:
            voice.amadeus_say(result["content"], self.message_queue)
        
        self.hide_loading()
        return "ai" if result["type"] == "text" else True
    
    def handle_manual_input(self, e):
        text = self.input_field.value.strip()
        if text:  # Убрали проверку is_processing
            self.add_message("Вы", text)
            self.input_field.value = ""
            self.show_loading()  # Показываем загрузку
            threading.Thread(target=lambda: self.handle_command(text), daemon=True).start()