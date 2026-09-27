import asyncio
import difflib
import json
import os
import re
import tempfile
import threading
import time
import uuid
import wave
import winsound
from datetime import datetime

import ollama
import requests
import edge_tts
import pygame
import sounddevice as sd
from piper import PiperVoice
from vosk import Model, KaldiRecognizer

try:
    from duckduckgo_search import DDGS
except ImportError:
    from ddgs import DDGS  # на случай нового названия пакета

MODEL_PATH = "vosk-model-small-ru-0.22"
VOICE_OFFLINE = "ru_RU-irina-medium.onnx"
VOICE_EDGE = "ru-RU-SvetlanaNeural"
ALARMS_FILE = "alarms.json"
AI_MODEL = "qwen2.5:7b"  # если тянете 3b — верните "qwen2.5:3b"

CITY = "Санкт-Петербург"
CITY_LAT = 59.94
CITY_LON = 30.31

SYSTEM_PROMPT = (
    "Ты — Амадэус, личный голосовой ассистент. Отвечай ТОЛЬКО на русском языке. "
    "Никогда не используй иероглифы, английские вставки или другие языки. "
    "Отвечай коротко (1-3 предложения), живым языком. Ответ будет озвучен голосом, "
    "поэтому без списков, без markdown, без эмодзи."
)

voice_offline = PiperVoice.load(VOICE_OFFLINE)
pygame.mixer.init()
vosk_model = Model(MODEL_PATH)

# ---------- Озвучка ----------

async def edge_say(text):
    path = os.path.join(tempfile.gettempdir(), f"amadeus_{uuid.uuid4().hex}.mp3")
    communicate = edge_tts.Communicate(text, VOICE_EDGE)
    await communicate.save(path)
    return path

def amadeus_say(text):
    try:
        path = asyncio.run(edge_say(text))
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        os.remove(path)
        print(f"Амадэус: {text}")
    except Exception as e:
        print(f"Онлайн-голос не сработал, причина: {e}")
        with wave.open("speech.wav", "wb") as wav_file:
            voice_offline.synthesize_wav(text, wav_file)
        winsound.PlaySound("speech.wav", winsound.SND_FILENAME)

# ---------- ИИ ----------

ai_history = []

def ai_ask(text):
    """Отправить фразу в модель с контекстом диалога."""
    try:
        ai_history.append({"role": "user", "content": text})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + ai_history[-10:]
        response = ollama.chat(model=AI_MODEL, messages=messages,
                               options={"temperature": 0.7})
        answer = response["message"]["content"].strip()
        ai_history.append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return None

# ---------- Поиск в интернете ----------

def search_web(query, max_results=5):
    """Поиск в DuckDuckGo. Вернёт список результатов или None."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return None

def ai_ask_with_search(question):
    """Поищет в интернете и заставит ИИ ответить, опираясь на найденное."""
    results = search_web(question)
    if not results:
        return "Ничего не нашёл в интернете. Попробуйте переформулировать."

    context_parts = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        context_parts.append(f"- {title}: {body}")
    context_text = "\n".join(context_parts)

    print("--- Источники ---")
    for r in results:
        print(f"  {r.get('title')} | {r.get('href')}")
    print("-----------------")

    grounded = (
        f"Вопрос пользователя: {question}\n\n"
        f"Вот что нашлось в интернете:\n{context_text}\n\n"
        "Ответь на вопрос, опираясь ТОЛЬКО на эти данные (1-3 предложения). "
        "Если в данных нет ответа — честно скажи, что не нашёл, не выдумывай."
    )
    return ai_ask(grounded)

# ---------- Слушание ----------

def amadeus_listen(say_first=None, discard_seconds=1.5, timeout_seconds=None):
    """Слушать микрофон. Ждёт 2 сек тишины после речи (можно говорить с паузами).
    timeout_seconds — максимум ожидания начала речи (для диалога с ИИ)."""
    recognizer = KaldiRecognizer(vosk_model, 16000)
    final_text = ""
    last_speech_time = time.time()
    started = False

    with sd.RawInputStream(samplerate=16000, blocksize=8000,
                           dtype='int16', channels=1) as stream:
        if say_first:
            amadeus_say(say_first)
            for _ in range(int(discard_seconds / 0.25)):
                stream.read(4000)

        print("Говорите...")
        while True:
            data, _ = stream.read(4000)
            if recognizer.AcceptWaveform(bytes(data)):
                text = json.loads(recognizer.Result()).get("text", "")
                if text.strip():
                    final_text = text
                    started = True
                if time.time() - last_speech_time > 2.0:
                    break
            else:
                partial = json.loads(recognizer.PartialResult()).get("partial", "")
                if partial.strip():
                    last_speech_time = time.time()
                    started = True

            if timeout_seconds and not started and time.time() - last_speech_time > timeout_seconds:
                break

    if not final_text.strip():
        final_text = json.loads(recognizer.PartialResult()).get("partial", "")
    return final_text

# ---------- Утилиты ----------

def fuzzy_contains(text, word, cutoff=0.75):
    words = text.split()
    return any(difflib.SequenceMatcher(None, w, word).ratio() >= cutoff for w in words)

# ---------- Будильники ----------

def load_alarms():
    if os.path.exists(ALARMS_FILE):
        with open(ALARMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_alarms(alarms):
    with open(ALARMS_FILE, "w", encoding="utf-8") as f:
        json.dump(alarms, f, ensure_ascii=False, indent=2)

ONES = {"ноль": 0, "час": 1, "один": 1, "два": 2, "три": 3, "четыре": 4,
        "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
        "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
        "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
        "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19}
TENS = {"двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50}

def words_to_number(words):
    total = 0
    for w in words:
        if w in ONES:
            total += ONES[w]
        elif w in TENS:
            total += TENS[w]
        else:
            return None
    return total if words else None

def parse_time(text):
    m = re.search(r"(\d{1,2})\s*[:\s]\s*(\d{2})", text)
    if m:
        return int(m.group(1)), int(m.group(2))

    words = text.replace(":", " ").split()
    if "на" in words:
        words = words[words.index("на") + 1:]
    elif "в" in words:
        words = words[words.index("в") + 1:]
    words = [w for w in words if w not in ("часов", "минут", "минуты", "часа")]
    for split in range(len(words) - 1, 0, -1):
        h = words_to_number(words[:split])
        mnt = words_to_number(words[split:])
        if h is not None and mnt is not None and h <= 23 and mnt <= 59:
            return h, mnt
    return None

def set_alarm(text):
    parsed = parse_time(text)
    if not parsed:
        amadeus_say("Не понял время. Скажите, например: поставь будильник на 7 30")
        return
    h, mnt = parsed
    alarms = load_alarms()
    alarm = {"hour": h, "minute": mnt}
    if alarm in alarms:
        amadeus_say(f"Будильник на {h} {mnt} уже стоит.")
        return
    alarms.append(alarm)
    save_alarms(alarms)
    amadeus_say(f"Будильник поставлен на {h} часов {mnt} минут.")

def remove_alarm(text, silent=False):
    parsed = parse_time(text)
    alarms = load_alarms()
    if parsed:
        h, mnt = parsed
        alarm = {"hour": h, "minute": mnt}
        if alarm in alarms:
            alarms.remove(alarm)
            save_alarms(alarms)
            if not silent:
                amadeus_say(f"Будильник на {h} {mnt} удалён.")
            return
        if not silent:
            amadeus_say(f"Будильника на {h} {mnt} нет.")
        return
    fired = getattr(remove_alarm, "last_fired", None)
    if fired and fired in alarms:
        alarms.remove(fired)
        save_alarms(alarms)
        if not silent:
            amadeus_say(f"Будильник на {fired['hour']} {fired['minute']} удалён.")
    elif not silent:
        amadeus_say("Не понял, какой будильник удалить.")

def list_alarms():
    alarms = load_alarms()
    if not alarms:
        amadeus_say("Будильников нет.")
        return
    alarms.sort(key=lambda a: (a["hour"], a["minute"]))
    phrases = [f"на {a['hour']} {a['minute']}" for a in alarms]
    amadeus_say("У вас стоят будильники: " + ", ".join(phrases))

def alarm_watcher():
    while True:
        now = datetime.now()
        alarms = load_alarms()
        for a in alarms:
            if a["hour"] == now.hour and a["minute"] == now.minute and now.second < 20:
                remove_alarm.last_fired = a
                amadeus_say(f"Проснись! Время {a['hour']} часов {a['minute']} минут. Это Амадэус, вставай!")
                time.sleep(1)
                answer = amadeus_listen(say_first="Это разовый будильник. Удалить его?")
                print(f"Ответ: {answer}")
                if any(w in answer for w in ("да", "удали", "конечно", "давай", "ага", "угу")):
                    remove_alarm("")
                else:
                    amadeus_say("Оставляю будильник.")
        time.sleep(10)

# ---------- Погода ----------

def describe_weather(code):
    if code == 0: return "ясно"
    if code in (1, 2): return "переменная облачность"
    if code == 3: return "пасмурно"
    if code in (45, 48): return "туман"
    if code in (51, 53, 55, 56, 57): return "морось"
    if code in (61, 63, 65, 80, 81, 82): return "дождь"
    if code in (66, 67): return "ледяной дождь"
    if code in (71, 73, 75, 77, 85, 86): return "снег"
    if code in (95, 96, 99): return "гроза"
    return "непонятная погода"

def get_weather():
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={CITY_LAT}"
           f"&longitude={CITY_LON}&current=temperature_2m,weathercode,"
           f"wind_speed_10m,apparent_temperature&timezone=auto")
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        current = data["current"]
        temp = round(current["temperature_2m"])
        feels = round(current["apparent_temperature"])
        desc = describe_weather(current["weathercode"])
        wind = round(current["wind_speed_10m"])
        return (f"Сейчас в городе {CITY} {desc}, температура {temp} градусов, "
                f"ощущается как {feels}. Ветер {wind} метров в секунду.")
    except Exception as e:
        print(f"Ошибка запроса погоды: {e}")
        return None

# ---------- Команды ----------

def handle_command(text):
    """Вернёт: True (команда выполнена), False (выход), 'ai' (ответил ИИ)."""
    if fuzzy_contains(text, "время") or "который час" in text or "сколько времени" in text:
        now = datetime.now()
        amadeus_say(f"Сейчас {now.hour} часов {now.minute} минут")
    elif fuzzy_contains(text, "погода") or "погоду" in text:
        amadeus_say("Секунду, ищу в интернете.")
        weather_text = get_weather()
        if weather_text:
            amadeus_say(weather_text)
        else:
            amadeus_say("Не удалось узнать погоду. Проверьте интернет.")
    elif fuzzy_contains(text, "будильник") and any(w in text for w in ("удали", "отмени", "выключи", "убери")):
        remove_alarm(text)
    elif fuzzy_contains(text, "будильник") and any(w in text for w in ("какие", "какой", "список", "покажи", "остались")):
        list_alarms()
    elif fuzzy_contains(text, "будильник"):
        set_alarm(text)
    elif any(text.startswith(w) for w in ("поищи", "найди", "загугли", "погугли")):
        query = text
        for w in ("поищи", "найди", "загугли", "погугли"):
            if text.startswith(w):
                query = text[len(w):].strip()
                break
        amadeus_say("Секунду, ищу в интернете.")
        answer = ai_ask_with_search(query)
        amadeus_say(answer)
        return "ai"
    elif any(w in text for w in ("стоп", "выход", "пока", "выключись", "хватит")):
        alarms = load_alarms()
        if alarms:
            answer = amadeus_listen(say_first=f"Выключаюсь. У вас осталось {len(alarms)} будильников. Очистить их все?")
            print(f"Ответ: {answer}")
            if any(w in answer for w in ("да", "очисти", "конечно", "давай", "ага", "угу", "удали")):
                save_alarms([])
                amadeus_say("Все будильники удалены. До встречи!")
            else:
                amadeus_say("Оставляю будильники. До встречи!")
        else:
            amadeus_say("Выключаюсь. До встречи!")
        return False
    else:
        amadeus_say("Секунду, думаю.")
        answer = ai_ask(text)
        if answer:
            amadeus_say(answer)
            return "ai"
        else:
            amadeus_say("Не смог ответить. Проверьте, запущена ли модель.")
    return True

# ---------- Активация по слову ----------

def wait_for_wake_word():
    recognizer = KaldiRecognizer(vosk_model, 16000)

    print("Жду команду... (скажите «Амадэус»)")
    with sd.RawInputStream(samplerate=16000, blocksize=8000,
                           dtype='int16', channels=1) as stream:
        while True:
            data, _ = stream.read(4000)
            if recognizer.AcceptWaveform(bytes(data)):
                text = json.loads(recognizer.Result()).get("text", "")
            else:
                text = json.loads(recognizer.PartialResult()).get("partial", "")

            if "амаде" in text:
                return True

# ---------- Запуск ----------

threading.Thread(target=alarm_watcher, daemon=True).start()
amadeus_say("Привет! Я Амадэус. Позовите меня по имени, когда будете готовы.")

while True:
    wait_for_wake_word()
    text = amadeus_listen(say_first="Слушаю вас.")
    print(f"Вы сказали: {text}")

    if not text.strip():
        amadeus_say("Я вас не расслышал.")
        continue

    result = handle_command(text)
    if result is False:
        break

    # Если ответила ИИ — продолжаем диалог без повторного вызова имени
    while result == "ai":
        follow = amadeus_listen(timeout_seconds=30)
        if not follow.strip():
            amadeus_say("Если что — позовите меня по имени.")
            break
        print(f"Вы сказали: {follow}")
        result = handle_command(follow)
        if result is False:
            break