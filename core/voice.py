import asyncio
import json
import os
import tempfile
import uuid
import wave
import winsound
import time
import sounddevice as sd
import pygame
import config
from vosk import Model, KaldiRecognizer
pygame.mixer.init()

# Загрузка Vosk модели
try:
    vosk_model = Model(config.MODEL_PATH)
    print(f"✅ Vosk модель загружена: {config.MODEL_PATH}")
except Exception as e:
    print(f"❌ Не удалось загрузить модель Vosk: {e}")
    vosk_model = None

# Загрузка Piper (оффлайн голос)
voice_offline = None
try:
    if os.path.exists(config.VOICE_OFFLINE):
        from piper import PiperVoice
        voice_offline = PiperVoice.load(config.VOICE_OFFLINE)
        print(f"✅ Piper голос загружен: {config.VOICE_OFFLINE}")
    else:
        print(f"️ Файл голоса не найден: {config.VOICE_OFFLINE}")
except ImportError:
    print("⚠️ Piper не установлен, оффлайн голос недоступен")
except Exception as e:
    print(f"⚠️ Ошибка загрузки Piper: {e}")

# --- GOOGLE TTS ---
async def google_say(text):
    """Google TTS - бесплатный и стабильный"""
    from gtts import gTTS
    path = os.path.join(tempfile.gettempdir(), f"amadeus_{uuid.uuid4().hex}.mp3")
    tts = gTTS(text=text, lang='ru')
    tts.save(path)
    return path

# --- EDGE TTS (Microsoft) ---
async def edge_say(text):
    """Microsoft Edge TTS - голос Светлана (может отвалиться)"""
    import edge_tts
    path = os.path.join(tempfile.gettempdir(), f"amadeus_{uuid.uuid4().hex}.mp3")
    communicate = edge_tts.Communicate(text, config.VOICE_EDGE)
    await communicate.save(path)
    return path

# --- PIPER (оффлайн) ---
def piper_say(text):
    """Оффлайн голос Piper - Ирина"""
    if not voice_offline:
        raise Exception("Piper не загружен")
    with wave.open("speech.wav", "wb") as wav_file:
        voice_offline.synthesize_wav(text, wav_file)
    winsound.PlaySound("speech.wav", winsound.SND_FILENAME)

# --- ГЛАВНАЯ ФУНКЦИЯ ОЗВУЧКИ ---
def amadeus_say(text, message_queue):
    print(f"🗣️ Амадэус: {text}")
    if message_queue:
        message_queue.put(("Амадэус", text))
    
    provider = config.VOICE_PROVIDER.lower()
    
    try:
        if provider == "gtts":
            print("[INFO] Используем gTTS (Google Text-to-Speech)...")
            path = asyncio.run(google_say(text))
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            os.remove(path)
            
        elif provider == "edge":
            print(f"[INFO] Используем Edge TTS (Microsoft, голос: {config.VOICE_EDGE})...")
            path = asyncio.run(edge_say(text))
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            os.remove(path)
            
        elif provider == "piper":
            print("[INFO] Используем Piper (оффлайн, голос Ирина)...")
            piper_say(text)
            
        else:
            print(f"[ERROR] Неизвестный провайдер: {provider}")
            
    except Exception as e:
        print(f"[WARN] {provider.upper()} не сработал ({e}), пробую Piper...")
        try:
            piper_say(text)
        except Exception as e2:
            print(f"[ERROR] Ошибка Piper: {e2}")


def wait_for_wake_word():
    """Ждёт, пока пользователь скажет слово активации 'Амадэус'"""
    if not vosk_model:
        time.sleep(1)
        return True  # Пропускаем, если модели нет
    
    recognizer = KaldiRecognizer(vosk_model, 16000)
    print("👂 Жду команду... (скажите Амадэус)")
    
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1) as stream:
        while True:
            data, _ = stream.read(4000)
            if recognizer.AcceptWaveform(bytes(data)):
                text = json.loads(recognizer.Result()).get("text", "")
            else:
                text = json.loads(recognizer.PartialResult()).get("partial", "")

            if "амаде" in text or "аманде" in text or "аматеус" in text or "амадеус" in text:
                return True

def amadeus_listen(say_first=None, timeout_seconds=30, say_callback=None):
    """Слушает речь пользователя и возвращает распознанный текст"""
    if not vosk_model:
        print("[WARN] Vosk модель не загружена, распознавание недоступно")
        return ""
        
    recognizer = KaldiRecognizer(vosk_model, 16000)
    final_text = ""
    last_speech_time = time.time()
    started = False

    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1) as stream:
        if say_first and say_callback:
            say_callback(say_first, None)
            for _ in range(6): 
                stream.read(4000)

        print("🎤 Говорите...")
        while True:
            data, _ = stream.read(4000)
            if recognizer.AcceptWaveform(bytes(data)):
                text = json.loads(recognizer.Result()).get("text", "")
                if text.strip():
                    final_text = text
                    started = True
                if time.time() - last_speech_time > 2.0 and started:
                    break
            else:
                partial = json.loads(recognizer.PartialResult()).get("partial", "")
                if partial.strip():
                    last_speech_time = time.time()
                    started = True

            if not started and time.time() - last_speech_time > timeout_seconds:
                break

    if not final_text.strip():
        final_text = json.loads(recognizer.PartialResult()).get("partial", "")
    return final_text