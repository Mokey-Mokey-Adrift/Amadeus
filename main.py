import asyncio
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

import requests
import edge_tts
import pygame
import sounddevice as sd
from piper import PiperVoice
from vosk import Model, KaldiRecognizer

MODEL_PATH = "vosk-model-small-ru-0.22"
VOICE_OFFLINE = "ru_RU-irina-medium.onnx"
VOICE_EDGE = "ru-RU-SvetlanaNeural"
ALARMS_FILE = "alarms.json"

CITY = "Москва"  # ваш город
CITY_LAT = 55.75   # широта
CITY_LON = 37.61   # долгота

voice_offline = PiperVoice.load(VOICE_OFFLINE)
pygame.mixer.init()

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

# ---------- Слушание ----------

def amadeus_listen():
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)

    print("Говорите...")
    with sd.RawInputStream(samplerate=16000, blocksize=8000,
                           dtype='int16', channels=1) as stream:
        while True:
            data, _ = stream.read(4000)
            if recognizer.AcceptWaveform(bytes(data)):
                break

    result = json.loads(recognizer.Result())
    return result.get("text", "")

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
    for split in range(1, len(words)):
        h = words_to_number(words[:split])
        mnt = words_to_number(words[split:])
        if h is not None and mnt is not None:
            return h, mnt
    return None

def set_alarm(text):
    parsed = parse_time(text)
    if not parsed:
        amadeus_say("Не понял время. Скажите, например: поставь будильник на 7 30")
        return
    h, mnt = parsed
    if not (0 <= h <= 23 and 0 <= mnt <= 59):
        amadeus_say("Такого времени не бывает. Часы от 0 до 23, минуты от 0 до 59.")
        return
    alarms = load_alarms()
    alarm = {"hour": h, "minute": mnt}
    if alarm in alarms:
        amadeus_say(f"Будильник на {h} {mnt} уже стоит.")
        return
    alarms.append(alarm)
    save_alarms(alarms)
    amadeus_say(f"Будильник поставлен на {h} часов {mnt} минут.")

def remove_alarm(text):
    parsed = parse_time(text)
    if not parsed:
        amadeus_say("Не понял, какой будильник удалить.")
        return
    h, mnt = parsed
    alarms = load_alarms()
    alarm = {"hour": h, "minute": mnt}
    if alarm in alarms:
        alarms.remove(alarm)
        save_alarms(alarms)
        amadeus_say(f"Будильник на {h} {mnt} удалён.")
    else:
        amadeus_say(f"Будильника на {h} {mnt} нет.")

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
                amadeus_say(f"Проснись! Время {a['hour']} часов {a['minute']} минут. Это Амадэус, вставай!")
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
    if "время" in text or "который час" in text or "сколько времени" in text:
        now = datetime.now()
        amadeus_say(f"Сейчас {now.hour} часов {now.minute} минут")
    elif "погода" in text or "погоду" in text:
        amadeus_say("Секунду, ищу в интернете.")
        weather_text = get_weather()
        if weather_text:
            amadeus_say(weather_text)
        else:
            amadeus_say("Не удалось узнать погоду. Проверьте интернет.")
    elif "будильник" in text and ("удали" in text or "отмени" in text):
        remove_alarm(text)
    elif "будильник" in text and ("какие" in text or "какой" in text or "список" in text or "покажи" in text):
        list_alarms()
    elif "будильник" in text:
        set_alarm(text)
    elif "стоп" in text or "выход" in text or "пока" in text:
        amadeus_say("Выключаюсь. До встречи!")
        return False
    else:
        amadeus_say(f"Вы сказали: {text}")
    return True

# ---------- Активация по слову ----------

def wait_for_wake_word():
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)

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
    amadeus_say("Слушаю вас.")
    text = amadeus_listen()
    print(f"Вы сказали: {text}")

    if not text.strip():
        amadeus_say("Я вас не расслышал.")
        continue

    if not handle_command(text):
        break