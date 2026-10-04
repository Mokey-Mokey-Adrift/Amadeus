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

SYSTEM_PROMPT = """Ты — Амадэус, голосовой ассистент. Отвечай кратко (1-3 предложения).

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

Если не знаешь ответа — честно скажи об этом."""

def ask_ai(text: str, chat_history: list):
    """Получаем запрос от пользователя и решаем, вызывать функцию или нет.
    chat_history — список сообщений только текущего чата."""
    
    if not config.API_KEY or config.API_KEY == "ТВОЙ_КЛЮЧ_ОТ_PROXYAPI":
        return {"type": "text", "content": "Ошибка: не указан API ключ в config.py"}
    
    try:
        # Формируем сообщения: системный промпт + история текущего чата + новый запрос
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Добавляем историю текущего чата (ограничиваем MAX_HISTORY)
        for msg in chat_history[-MAX_HISTORY:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Добавляем текущий запрос
        messages.append({"role": "user", "content": text})
        
        response = client.chat.completions.create(
            model=config.AI_MODEL,
            messages=messages,
            tools=BASE_TOOLS,
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
        return {"type": "text", "content": "Извини, проблемы со связью с моим мозгом."}

def finalize_tool_response(tool_call_id: str, tool_result_content: str, chat_history: list):
    """ИИ получает результат функции и формулирует красивый ответ.
    chat_history — история текущего чата."""
    
    try:
        # Формируем сообщения с результатом функции
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
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