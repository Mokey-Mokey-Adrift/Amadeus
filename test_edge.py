import asyncio
import edge_tts

async def main():
    communicate = edge_tts.Communicate(
        "Проверка голоса Светланы", "ru-RU-SvetlanaNeural"
    )
    await communicate.save("test.mp3")
    print("Файл test.mp3 сохранён — Светлана работает!")

asyncio.run(main())