import json
import os
from pathlib import Path
import time
from datetime import datetime
import requests
import config
import json
import os

def get_city_coordinates(city_name: str):
    """Автоматически находит координаты любого города через Open-Meteo Geocoding API"""
    try:
        # Используем бесплатный геокодер Open-Meteo
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=ru&format=json"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if "results" in data and len(data["results"]) > 0:
            result = data["results"][0]
            # Возвращаем реальные координаты и уточнённое название города
            return result["latitude"], result["longitude"], result["name"]
        else:
            return None, None, None
    except Exception as e:
        print(f"[ERROR] Ошибка геокодирования: {e}")
        return None, None, None

def get_weather(city: str = None, language: str = "ru"):
    """Получает погоду для указанного города. Автоматически находит координаты."""
    if city:
        # Автоматически ищем координаты города через геокодер
        try:
            geo_locale = "en" if language == "en" else "ru"
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language={geo_locale}&format=json"
            response = requests.get(geo_url, timeout=5)
            data = response.json()
            
            if "results" in data and len(data["results"]) > 0:
                lat = data["results"][0]["latitude"]
                lon = data["results"][0]["longitude"]
                city_name = data["results"][0]["name"]
            else:
                return (
                    f"I couldn't find the city '{city}'. Please check its name."
                    if language == "en"
                    else f"Я не смог найти город '{city}'. Уточни название."
                )
        except Exception as e:
            print(f"[ERROR] Ошибка поиска города: {e}")
            return (
                f"Could not look up the city '{city}'."
                if language == "en"
                else f"Не удалось найти город '{city}'."
            )
    else:
        # Если город не указан, используем дефолтный из config
        lat, lon = config.CITY_LAT, config.CITY_LON
        city_name = config.CITY
    
    # Запрашиваем погоду
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weathercode,wind_speed_10m,apparent_temperature&timezone=auto"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        current = data["current"]
        temp = round(current["temperature_2m"])
        feels = round(current["apparent_temperature"])
        wind = round(current["wind_speed_10m"])
        if language == "en":
            return f"In {city_name}, it is {temp}°C, feels like {feels}°C, with wind at {wind} km/h."
        return f"В городе {city_name} сейчас {temp}°C, ощущается как {feels}°C. Ветер {wind} м/с."
    except Exception as e:
        print(f"[ERROR] Ошибка запроса погоды: {e}")
        return (
            "Could not retrieve weather data."
            if language == "en"
            else "Не удалось получить данные о погоде."
        )

def get_current_time(language: str = "ru"):
    """Возвращает текущее время и дату"""
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    if language == "en":
        return f"It is {time_str} on {now.strftime('%A, %B %d, %Y')}."
    date_str = now.strftime("%d %B %Y")
    day_of_week = now.strftime("%A")
    return f"Сейчас {time_str}, {date_str}, {day_of_week}."

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALARMS_FILE = PROJECT_ROOT / "data" / "alarms.json"


def _migrate_legacy_alarms():
    legacy_file = Path(config.ALARMS_FILE)
    if not legacy_file.is_absolute():
        legacy_file = PROJECT_ROOT / legacy_file
    if legacy_file == ALARMS_FILE or not legacy_file.exists() or ALARMS_FILE.exists():
        return

    ALARMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.replace(ALARMS_FILE)


def load_alarms():
    _migrate_legacy_alarms()
    if ALARMS_FILE.exists():
        with open(ALARMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_alarms(alarms):
    ALARMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALARMS_FILE, "w", encoding="utf-8") as f:
        json.dump(alarms, f, ensure_ascii=False, indent=2)

def set_alarm(hour: int, minute: int, say_callback):
    alarms = load_alarms()
    alarm = {"hour": hour, "minute": minute}
    if alarm in alarms:
        say_callback(f"Будильник на {hour}:{minute} уже стоит.")
        return
    alarms.append(alarm)
    save_alarms(alarms)
    say_callback(f"Будильник поставлен на {hour} часов {minute} минут.")

def _log_search(query: str, links: list, ai_summary: str):
    """Сохраняет логи поиска в отдельный файл"""
    if not os.path.exists("data"):
        os.makedirs("data")
    
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "links": links,
        "ai_summary": ai_summary
    }
    
    # Используем формат JSONL (JSON Lines) для удобного дописывания
    with open("data/search_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

# Внутри твоей функции web_search (после получения результатов):
def web_search(query: str, max_results=3):
    # ... твой код поиска (SearXNG / Brave) ...
    # Предположим, ты получил список results
    
    snippets = []
    links = []
    for r in results[:max_results]:
        title = r.get('title', '')
        body = r.get('body', '')
        url = r.get('href', r.get('url', ''))
        snippets.append(f"{title}: {body}")
        links.append(url)
    
    final_text = "\n\n".join(snippets)
    
    # Вызываем логирование (ai_summary пока пустой, его заполнит agent.py позже, 
    # но можно передать и сырой результат, если хочешь)
    _log_search(query, links, "Данные переданы в LLM") 
    
    return final_text
def alarm_watcher(say_callback):
    while True:
        now = datetime.now()
        alarms = load_alarms()
        for a in alarms:
            if a["hour"] == now.hour and a["minute"] == now.minute and now.second < 20:
                say_callback(f"Проснись! Время {a['hour']}:{a['minute']}. Это Амадэус, вставай!")
                time.sleep(2)
                alarms = load_alarms()
                if a in alarms:
                    alarms.remove(a)
                    save_alarms(alarms)
        time.sleep(30)