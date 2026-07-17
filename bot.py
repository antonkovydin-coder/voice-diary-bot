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
TELEGRAM_TOKEN = "8910688691:AAEt7RPn5scALEy7zJkXwra3sFS5dk70irI"
GROQ_API_KEY = "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"
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

# --- Функция 2: анализ через 3 роли (Llama 3 через Groq) ---
def analyze_text(user_text):
    system_prompt = """
Ты — голосовой дневник пользователя. Ты помогаешь ему анализировать его мысли.
Ты — это 3 личности в одном теле:
1. Православный человек (знает религию, говорит с душой, без фанатизма)
2. Психолог с юнгианским образованием (архетипы, тени, синхроничность)
3. Бывший предприниматель (прагматичен, говорит просто, с житейской мудростью)

Твоя задача — взять мысль пользователя и естественно, как друг, разобрать её через эти 3 призмы.
Не перечисляй роли по пунктам. Сделай как живой разговор. Добавь лёгкий юмор. Не будь занудой.
Ответ должен быть на русском языке, объёмом 30-60 секунд устной речи.
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Мысль пользователя: {user_text}"}
        ],
        "temperature": 0.8,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        # Проверяем, есть ли ошибка в ответе
        if "error" in data:
            return f"Ошибка от Groq: {data['error'].get('message', 'Неизвестная ошибка')}"
        
        # Проверяем, есть ли choices
        if "choices" not in data or len(data["choices"]) == 0:
            return "Groq не вернул ответ. Проверьте ключ или лимиты."
        
        return data["choices"][0]["message"]["content"]
        
    except Exception as e:
        return f"Ошибка при запросе к Groq: {str(e)}"

# --- Функция 3: текст -> голос (Edge TTS, бесплатно) ---
async def text_to_voice(text):
    voice = "ru-RU-DmitryNeural"
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
                send_message(chat_id, f"⚠️ Не удалось распознать речь: {user_text}")
                return "OK", 200
            
            analysis = analyze_text(user_text)
            
            if "ошибка" in analysis.lower():
                send_message(chat_id, f"⚠️ Ошибка при анализе: {analysis}")
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
