# ui/interface.py
import flet as ft
import threading
import queue
from core import voice, agent, tools
from core import chat_manager

# Цвета Steins;Gate
COLOR_BG = "#1a1a1a"
COLOR_SURFACE = "#1a1a1a"
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
        self.is_processing = False
        self.sidebar_visible = True
        self._queue_checker_active = True
        self._renaming_chat_id = None
        self._rename_previous_input = ""
        
        page.title = "Amadeus v0.4"
        page.bgcolor = COLOR_BG
        theme = ft.Theme(
            color_scheme_seed=ft.Colors.GREY,  # Базовый цвет темы
            color_scheme=ft.ColorScheme(
                surface=COLOR_SURFACE,
            ),
        )
        page.theme = theme
        page.dark_theme = theme
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 0
        page.window_width = 1000
        page.window_height = 700
        page.window.on_event = self._handle_window_event
        
        # 1. Сайдбар
        self.sidebar_header = ft.Row(
            [
                ft.Text("ЧАТЫ", color=COLOR_ACCENT, weight="bold", size=14),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    icon_color=COLOR_TEXT,
                    on_click=self.create_new_chat_ui,
                    icon_size=18,
                ),
            ]
        )
        self.sidebar_list = ft.Column(
            controls=[],
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
        )
        self.sidebar_content = ft.Column(
            controls=[
                self.sidebar_header,
                ft.Container(height=1, bgcolor=COLOR_SURFACE),
                self.sidebar_list,
            ],
            expand=True,
            spacing=0,
        )
        self.sidebar = ft.Container(
            content=self.sidebar_content,
            width=200,
            bgcolor=COLOR_BG,
            padding=8,
        )
        
        # 2. Элементы основной области
        self.chat_column = ft.Column(expand=True, spacing=10, scroll=ft.ScrollMode.AUTO)
        
        self.input_field = ft.TextField(
            hint_text="Введите команду...",
            expand=True,
            bgcolor=COLOR_SURFACE,
            color=COLOR_TEXT,
            border_radius=10,
            text_size=14,
            min_lines=1,
            max_lines=5,
            on_submit=self.handle_manual_input,
        )
        
        self.send_btn = ft.IconButton(
            icon=ft.Icons.SEND, 
            icon_color=COLOR_ACCENT, 
            on_click=self.handle_manual_input
        )
        self.cancel_rename_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_color=COLOR_TEXT_DIM,
            visible=False,
            tooltip="Отменить переименование",
            on_click=self.cancel_chat_rename,
        )
        self.rename_hint = ft.Text(
            "Переименование чата: измените название в поле внизу и нажмите ✓",
            color=COLOR_ACCENT,
            size=12,
            visible=False,
        )
        
        self.loading_indicator = ft.ProgressRing(width=20, height=20, stroke_width=2, color=COLOR_ACCENT)
        self.send_container = ft.Container(content=self.send_btn, width=40, height=40)
        
        self.voice_btn = ft.Button(
            content=ft.Text("Голос", color=COLOR_TEXT, weight="bold"),
            icon=ft.Icons.MIC, 
            bgcolor=COLOR_ACCENT, 
            on_click=self.toggle_voice
        )
        
        # ← ВОТ СЮДА вставь кнопку гамбургер (сразу после voice_btn):
        self.toggle_sidebar_icon = ft.Icon(ft.Icons.MENU_OPEN, color=COLOR_TEXT_DIM, size=20)
        self.toggle_sidebar_btn = ft.Container(
            content=self.toggle_sidebar_icon,
            padding=8,
            on_click=self.toggle_sidebar,
            border_radius=8,
        )

        # 3. Основная область
        self.main_column = ft.Column([
            ft.Row(
                [
                    self.toggle_sidebar_btn,
                    ft.Text("AMADEUS", size=24, weight="bold", color=COLOR_ACCENT, expand=True),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            self.chat_column,
            self.rename_hint,
            ft.Row(
                [
                    self.input_field,
                    self.cancel_rename_btn,
                    self.send_container,
                    self.voice_btn,
                ],
                spacing=10
            )
        ], expand=True)
        
        # 4. Главный Row
        self.main_row = ft.Row([
            self.sidebar,
            self.main_column
        ], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        
        self.refresh_sidebar(update=False)
        page.add(self.main_row)
        self.load_active_chat_to_ui()
        self.page.run_task(self._start_queue_checker)

        
    # --- ЛОГИКА САЙДБАРА ---
    def refresh_sidebar(self, update=True):
        data = chat_manager.load_chats()
        items = []

        for chat in data["chats"]:
            is_active = chat["id"] == data["active_chat_id"]

            chat_button = ft.TextButton(
                content=chat["title"],
                expand=True,
                height=36,
                on_click=lambda e, cid=chat["id"]: self.switch_chat_ui(cid),
                style=ft.ButtonStyle(
                    color=COLOR_ACCENT if is_active else COLOR_TEXT,
                    bgcolor="#332014" if is_active else "transparent",
                    padding=8,
                    alignment=ft.Alignment.CENTER_LEFT,
                    text_style=ft.TextStyle(
                        size=13,
                        weight="bold" if is_active else "normal",
                    ),
                )
            )
            menu = ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT,
                icon_color=COLOR_ACCENT if is_active else COLOR_TEXT_DIM,
                icon_size=18,
                height=36,
                items=[
                    ft.PopupMenuItem(
                        content="Переименовать",
                        on_click=lambda e, cid=chat["id"]: self.begin_chat_rename(cid),
                    ),
                    ft.PopupMenuItem(
                        content="Удалить",
                        on_click=lambda e, cid=chat["id"]: self.delete_chat_ui(cid),
                    ),
                ],
            )
            row = ft.Row([chat_button, menu], spacing=0, height=36)

            items.append(row)
        
        self.sidebar_list.controls = items
        if update:
            self.page.update()

    def toggle_sidebar(self, e):
        self.sidebar_visible = not self.sidebar_visible
        self.sidebar.visible = self.sidebar_visible
        
        if self.sidebar_visible:
            self.toggle_sidebar_btn.content = ft.Icon(ft.Icons.MENU_OPEN, color=COLOR_TEXT_DIM, size=20)
        else:
            self.toggle_sidebar_btn.content = ft.Icon(ft.Icons.MENU, color=COLOR_TEXT_DIM, size=20)
        
        self.page.update()

    def create_new_chat_ui(self, e):
        new_id = chat_manager.create_new_chat()
        self.refresh_sidebar()
        self.load_active_chat_to_ui()

    def switch_chat_ui(self, chat_id):
        chat_manager.switch_chat(chat_id)
        self.refresh_sidebar()
        self.load_active_chat_to_ui()

    def delete_chat_ui(self, chat_id):
        chat_manager.delete_chat(chat_id)
        self.refresh_sidebar()
        self.load_active_chat_to_ui()

    def begin_chat_rename(self, chat_id):
        data = chat_manager.load_chats()
        chat = next((item for item in data["chats"] if item["id"] == chat_id), None)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        self._renaming_chat_id = chat_id
        self._rename_previous_input = self.input_field.value or ""
        self.input_field.value = chat["title"]
        self.input_field.hint_text = "Введите новое название..."
        self.send_btn.icon = ft.Icons.CHECK
        self.send_btn.tooltip = "Сохранить название чата"
        self.cancel_rename_btn.visible = True
        self.rename_hint.visible = True
        self.page.update()

    def save_chat_rename(self, chat_id):
        new_name = (self.input_field.value or "").strip()
        if new_name:
            chat_manager.rename_chat(chat_id, new_name)
        self._renaming_chat_id = None
        self.input_field.value = self._rename_previous_input
        self.input_field.hint_text = "Введите команду..."
        self._rename_previous_input = ""
        self.send_btn.icon = ft.Icons.SEND
        self.send_btn.tooltip = None
        self.cancel_rename_btn.visible = False
        self.rename_hint.visible = False
        self.refresh_sidebar()
        self.page.update()

    def cancel_chat_rename(self, e):
        if self._renaming_chat_id is None:
            return
        self._renaming_chat_id = None
        self.input_field.value = self._rename_previous_input
        self.input_field.hint_text = "Введите команду..."
        self._rename_previous_input = ""
        self.send_btn.icon = ft.Icons.SEND
        self.send_btn.tooltip = None
        self.cancel_rename_btn.visible = False
        self.rename_hint.visible = False
        self.page.update()

    # --- ЛОГИКА ЧАТА ---
    def load_active_chat_to_ui(self):
        self.chat_column.controls.clear()
        messages = chat_manager.get_active_chat_messages()
        for msg in messages:
            self.add_message_to_ui(msg["role"], msg["content"], update=False)
        self.page.update()

    def add_message_to_ui(self, sender, text, update=True):
        color = COLOR_USER if sender == "user" else COLOR_AMADEUS
        display_name = "Вы" if sender == "user" else "Амадэус"
        
        msg = ft.Row(
            [
                ft.Text(f"{display_name}:", color=color, weight="bold", size=13),
                ft.Text(text, color=COLOR_TEXT, size=14, expand=True)
            ],
            spacing=10
        )
        
        self.chat_column.controls.append(msg)
        if update:
            self.page.update()

    def handle_manual_input(self, e):
        text = self.input_field.value.strip()
        if not text: return

        if self._renaming_chat_id is not None:
            self.save_chat_rename(self._renaming_chat_id)
            return
        
        self.input_field.value = ""
        self.add_message_to_ui("user", text)
        chat_manager.add_message_to_active_chat("user", text)
        self.show_loading()
        
        threading.Thread(target=lambda: self.process_ai(text), daemon=True).start()

    def process_ai(self, text):
        chat_history = chat_manager.get_active_chat_messages()
        
        result = agent.ask_ai(text, chat_history)
        
        if result["type"] == "function":
            func_name = result["name"]
            args = result["args"]
            tool_id = result["tool_call_id"]
            print(f"️ Выполняем функцию: {func_name} с аргументами {args}")
            
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
            
            final_answer = agent.finalize_tool_response(tool_id, result_text, chat_history)
        else:
            final_answer = result["content"]
        
        self.page.run_task(self._finalize_response, final_answer)

    async def _finalize_response(self, text):
        self.hide_loading()
        self.add_message_to_ui("assistant", text)
        chat_manager.add_message_to_active_chat("assistant", text)
        self.refresh_sidebar()

    def show_loading(self):
        self.is_processing = True
        self.send_container.content = self.loading_indicator
        self.page.update()
    
    def hide_loading(self):
        self.is_processing = False
        self.send_container.content = self.send_btn
        self.page.update()

    def toggle_voice(self, e):
        if not self.is_running:
            self.is_running = True
            self.voice_btn.content = ft.Text("Стоп", color=COLOR_TEXT, weight="bold")
            self.voice_btn.icon = ft.Icons.STOP
            self.voice_btn.bgcolor = "#cc3300"
            self.page.update()
            print(" Запуск голосового режима...")
            threading.Thread(target=self.run_voice_loop, daemon=True).start()
        else:
            self.is_running = False
            self.voice_btn.content = ft.Text("▶ Голос", color=COLOR_TEXT, weight="bold")
            self.voice_btn.icon = ft.Icons.MIC
            self.voice_btn.bgcolor = COLOR_ACCENT
            self.page.update()
            print(" Голосовой режим остановлен")

    async def _start_queue_checker(self):
        import asyncio
        await asyncio.sleep(0.5)
        while self._queue_checker_active:
            self.check_queue()
            await asyncio.sleep(0.1)

    def check_queue(self):
        if not self._queue_checker_active:
            return

        try:
            while True:
                sender, text = self.message_queue.get_nowait()
                role = "user" if sender == "Вы" else "assistant"
                chat_manager.add_message_to_active_chat(role, text)
                self.add_message_to_ui(role, text)
        except queue.Empty:
            pass

    def _handle_window_event(self, e):
        if e.type == ft.WindowEventType.CLOSE:
            self._queue_checker_active = False

    def run_voice_loop(self):
        try:
            voice.amadeus_say("Привет! Я Амадэус. Позовите меня по имени.", self.message_queue)
            
            while self.is_running:
                print("👂 Жду слово активации...")
                voice.wait_for_wake_word()
                
                if not self.is_running:
                    break

                print(" Распознаю речь...")
                text = voice.amadeus_listen(
                    say_first="Слушаю вас.", 
                    timeout_seconds=15, 
                    say_callback=voice.amadeus_say
                )
                
                if text.strip():
                    print(f"📝 Распознано: {text}")
                    self.page.run_task(self._add_voice_message, "user", text)
                    chat_manager.add_message_to_active_chat("user", text)
                    self.page.run_task(self._process_voice_command, text)
                else:
                    print("️ Речь не распознана, жду снова...")
                    
        except Exception as ex:
            print(f"❌ Ошибка в голосовом режиме: {ex}")
            self.page.run_task(self._show_voice_error, str(ex))

    async def _add_voice_message(self, role, text):
        self.add_message_to_ui(role, text)

    async def _process_voice_command(self, text):
        self.show_loading()
        threading.Thread(target=lambda: self.process_ai(text), daemon=True).start()

    async def _show_voice_error(self, error_msg):
        self.add_message_to_ui("assistant", f"Ошибка голосового режима: {error_msg}")