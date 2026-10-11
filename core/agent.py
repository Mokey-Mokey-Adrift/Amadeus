# core/agent.py
from openai import OpenAI
import json
import config

client = OpenAI(
    api_key=config.API_KEY,
    base_url=config.BASE_URL,
    timeout=15.0
)

MAX_HISTORY = 15

BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_alarm",
            "description": "Устанавливает будильник на указанное время.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hour": {"type": "integer", "description": "Час (0-23)"},
                    "minute": {"type": "integer", "description": "Минуты (0-59)"}
                },
                "required": ["hour", "minute"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Получает текущую погоду в указанном городе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Название города на русском. Если не указан, используй город по умолчанию."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Ищет актуальную информацию в интернете. Используй ТОЛЬКО для новостей, событий, фактов, которые могли измениться после твоего обучения.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос на русском языке"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Возвращает текущее время и дату. Используй, когда пользователь спрашивает о времени, дате, дне недели или 'который час'.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

SYSTEM_PROMPTS = {
    "ru": """Ты — Амадэус, голосовой ассистент. Отвечай кратко (1-3 предложения).
Всегда отвечай на русском языке, если пользователь явно не попросил другой язык.

ПРАВИЛА ИСПОЛЬЗОВАНИЯ ИНСТРУМЕНТОВ:
1. Для погоды и будильников ВСЕГДА используй соответствующие функции.
2. Используй web_search ТОЛЬКО если:
   - Пользователь спрашивает о текущих событиях, новостях, погоде
   - Вопрос требует актуальной информации (цены, курсы валют, результаты матчей)
   - Ты не уверен в ответе или информация могла устареть
3. НЕ используй web_search для:
   - Общих знаний (что такое Python, кто написал книгу, объясни концепцию)
   - Вопросов о тебе самом или твоих возможностях
   - Простых приветствий и благодарностей

Если не знаешь ответа — честно скажи об этом.""",
    "en": """You are Amadeus, a voice assistant. Keep answers concise (1-3 sentences).
Always answer in English unless the user explicitly asks for another language.

TOOL USAGE RULES:
1. ALWAYS use the relevant functions for weather and alarms.
2. Use web_search ONLY when:
   - The user asks about current events, news, or current weather
   - The question requires up-to-date information (prices, exchange rates, match results)
   - You are unsure of the answer or the information may be outdated
3. Do NOT use web_search for:
   - General knowledge (what Python is, who wrote a book, or explaining a concept)
   - Questions about yourself or your capabilities
   - Simple greetings and thanks

If you do not know the answer, say so honestly.""",
}


def _tools_for_language(language):
    if language == "ru":
        return BASE_TOOLS

    tools = json.loads(json.dumps(BASE_TOOLS))
    descriptions = {
        "set_alarm": (
            "Sets an alarm for the specified time.",
            {"hour": "Hour (0-23)", "minute": "Minute (0-59)"},
        ),
        "get_weather": (
            "Gets the current weather for the specified city.",
            {"city": "City name. If omitted, use the default city."},
        ),
        "web_search": (
            "Searches the internet for current information. Use ONLY for news, events, "
            "or facts that may have changed since training.",
            {"query": "Search query in English."},
        ),
        "get_current_time": (
            "Returns the current time and date. Use when asked about the time, date, "
            "day of the week, or what time it is.",
            {},
        ),
    }
    for tool in tools:
        function = tool["function"]
        description, parameter_descriptions = descriptions[function["name"]]
        function["description"] = description
        for name, parameter_description in parameter_descriptions.items():
            function["parameters"]["properties"][name]["description"] = parameter_description
    return tools


def ask_ai(text: str, chat_history: list, language: str = "ru"):
    """Получаем запрос от пользователя и решаем, вызывать функцию или нет.
    chat_history — список сообщений только текущего чата."""
    
    if not config.API_KEY or config.API_KEY == "ТВОЙ_КЛЮЧ_ОТ_PROXYAPI":
        message = (
            "Error: API key is missing in config.py."
            if language == "en"
            else "Ошибка: не указан API ключ в config.py"
        )
        return {"type": "text", "content": message}
    
    try:
        # Формируем сообщения: системный промпт + история текущего чата + новый запрос
        messages = [{"role": "system", "content": SYSTEM_PROMPTS[language]}]
        
        # Добавляем историю текущего чата (ограничиваем MAX_HISTORY)
        for msg in chat_history[-MAX_HISTORY:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Добавляем текущий запрос
        messages.append({"role": "user", "content": text})
        
        response = client.chat.completions.create(
            model=config.AI_MODEL,
            messages=messages,
            tools=_tools_for_language(language),
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            print(f"[INFO] ИИ вызывает функцию: {tool_call.function.name}")
            
            return {
                "type": "function",
                "name": tool_call.function.name,
                "args": json.loads(tool_call.function.arguments),
                "tool_call_id": tool_call.id
            }
        
        response_text = message.content.strip()
        
        return {"type": "text", "content": response_text}
        
    except Exception as e:
        print(f"[ERROR] Ошибка API: {e}")
        message = (
            "Sorry, I am having trouble connecting to my brain."
            if language == "en"
            else "Извини, проблемы со связью с моим мозгом."
        )
        return {"type": "text", "content": message}


def finalize_tool_response(
    tool_call_id: str,
    tool_result_content: str,
    chat_history: list,
    language: str = "ru",
):
    """ИИ получает результат функции и формулирует красивый ответ.
    chat_history — история текущего чата."""
    
    try:
        # Формируем сообщения с результатом функции
        messages = [{"role": "system", "content": SYSTEM_PROMPTS[language]}]
        
        for msg in chat_history[-MAX_HISTORY:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Добавляем результат функции
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": tool_result_content
        })
        
        response = client.chat.completions.create(
            model=config.AI_MODEL,
            messages=messages
        )
        
        final_text = response.choices[0].message.content.strip()
        
        return final_text
        
    except Exception as e:
        print(f"[ERROR] Ошибка при финализации ответа: {e}")
        return tool_result_content