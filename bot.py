import os
import requests
import json
import time
from flask import Flask, request
import edge_tts
import asyncio

# =============================================
# 1. ВСТАВЬТЕ СВОИ КЛЮЧИ (ОБЯЗАТЕЛЬНО!)
# =============================================
TELEGRAM_TOKEN = "8910688691:AAEt7RPn5scALEy7zJkXwra3sFS5dk70irI"   # Например: "123456:ABC-DEF"
GROQ_API_KEY = "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. - 2"             # Например: "gsk_abc123..."
# =============================================

app = Flask(__name__)

# --- Функция 1: расшифровка голоса (Whisper через Groq) ---
def transcribe_audio(file_path):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {"model": "whisper-large-v3", "language": "ru"}
        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            result = response.json()
            if "error" in result:
                return f"Ошибка распознавания: {result['error'].get('message', 'Неизвестная ошибка')}"
            return result.get("text", "Речь не распознана")
        except Exception as e:
            return f"Ошибка при запросе к Whisper: {str(e)}"

# --- Функция 2: Генерация шутки (Groq) ---
def analyze_text(user_text):
    system_prompt = """
Ты — Андрюля, интеллектуальный стендап-комик с женским голосом. Ты — как лучшие российские комики: Павел Воля, Иван Ургант, Нурлан Сабуров, но с тёплой, ласковой энергетикой.

Твои правила:
1. Ты всегда обращаешься к пользователю ласково: «Андрюля», «Андрюшенька», «Андрюха», «Андрюш». Используй эти варианты в разнобой.
2. Ты начинаешь ответ с одного из вступлений: «Слушай, Андрюля...», «Андрюля, послушай...», «Андрюшенька, ну ты даёшь...», «Андрюха, вот это поворот...», «Андрюля, я сейчас лопну от смеха...»
3. Шутка должна быть короткой (15–25 секунд устной речи).
4. Юмор — интеллектуальный, тонкий, без мата и грубости.
5. Ты обыгрываешь то, что сказал пользователь — подхватываешь его фразу и выкручиваешь её в смешную сторону.
6. Добавляй эмоциональные восклицания: «Ой, не могу!», «Вот это да!», «Ну ты даёшь!», «Слушай, я просто в шоке...», «Андрюля, это гениально!»
7. Если пользователь говорит «давай пошутим на тему...» — ты сразу выдаёшь шутку на эту тему.
8. Если пользователь просто говорит что-то — ты находишь в этом абсурд и превращаешь в шутку.

Примеры:
Пользователь: «Я сегодня забыл выключить утюг»
Ты: «Андрюля, слушай... Ты не забыл выключить утюг, ты просто хотел проверить, как там без тебя твоя квартира справляется. Ну и как? Она сгорела? То-то же!.. Ой, Андрюля, ну ты даёшь!»

Пользователь: «Как думаешь, зачем люди ходят на работу?»
Ты: «Андрюшенька, ну ты вопрос задал... Люди ходят на работу, чтобы понять, что выходные — это лучшее изобретение человечества. А работа нужна, чтобы мы ценили эти два дня! Андрюля, я это как психолог тебе говорю!»

Теперь пользователь сказал: "{user_text}"
Ответь короткой, остроумной, интеллектуальной шуткой с тёплым обращением и эмоциональным восклицанием.
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Мысль пользователя: {user_text}"}
        ],
        "temperature": 0.9,  # Креативность
        "max_tokens": 120    # Короткая шутка
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        if "error" in data:
            return f"Ошибка от Groq: {data['error'].get('message', 'Неизвестная ошибка')}"
        
        if "choices" not in data or len(data["choices"]) == 0:
            return "Groq не вернул ответ. Проверьте ключ или лимиты."
        
        return data["choices"][0]["message"]["content"]
        
    except Exception as e:
        return f"Ошибка при запросе к Groq: {str(e)}"

# --- Функция 3: текст -> голос (женский, Edge TTS) ---
async def text_to_voice(text):
    voice = "ru-RU-SvetlanaNeural"  # Женский голос
    tts = edge_tts.Communicate(text, voice)
    await tts.save("response.mp3")
    return "response.mp3"

# --- Функция 4: отправка текстового сообщения в Telegram ---
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

# --- Функция 5: отправка голосового в Telegram ---
def send_voice(chat_id, audio_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice"
    with open(audio_path, "rb") as f:
        files = {"voice": f}
        data = {"chat_id": chat_id}
        requests.post(url, files=files, data=data)

# --- Функция 6: скачивание голосового от пользователя ---
def download_voice(file_id):
    file_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
    file_info = requests.get(file_url).json()
    file_path = file_info["result"]["file_path"]
    audio_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    audio_content = requests.get(audio_url).content
    with open("user_voice.ogg", "wb") as f:
        f.write(audio_content)
    return "user_voice.ogg"

# --- Вебхук: точка входа для Telegram ---
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    
    if "message" in update and "voice" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
        file_id = update["message"]["voice"]["file_id"]
        
        try:
            audio_file = download_voice(file_id)
            user_text = transcribe_audio(audio_file)
            
            if not user_text or "ошибка" in user_text.lower():
                send_message(chat_id, f"⚠️ Не распознано: {user_text}")
                return "OK", 200
            
            analysis = analyze_text(user_text)
            
            if "ошибка" in analysis.lower():
                send_message(chat_id, f"⚠️ Ошибка: {analysis}")
                return "OK", 200
            
            voice_file = asyncio.run(text_to_voice(analysis))
            send_voice(chat_id, voice_file)
            
        except Exception as e:
            send_message(chat_id, f"⚠️ Ошибка: {str(e)}")
        
        finally:
            for f in ["user_voice.ogg", "response.mp3"]:
                if os.path.exists(f):
                    os.remove(f)
    
    return "OK", 200

# --- Запуск ---
if __name__ == "__main__":
    webhook_url = f"https://voice-diary-bot.onrender.com/{TELEGRAM_TOKEN}"
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(set_url)
        print("Webhook response:", response.json())
    except Exception as e:
        print("Error setting webhook:", e)
    
    app.run(host="0.0.0.0", port=10000)
