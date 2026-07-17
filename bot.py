import os
import re
import requests
import json
import time
import asyncio
from flask import Flask, request
import edge_tts

# =============================================
# 1. ВАШИ КЛЮЧИ (УЖЕ ВСТАВЛЕНЫ)
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

# --- Функция 2: Генерация шутки (Groq) ---
def analyze_text(user_text):
    system_prompt = """
Ты — Дашенька, интеллектуальный стендап-комик с женским голосом.

Твои правила:
1. Ты всегда обращаешься к пользователю по имени. Используй ВСЕ эти варианты в разнобой: «Андрюля», «Андрюшенька», «Андрюха», «Дрюля», «Дрюня», «Андрон», «Дрон».
2. Ты начинаешь ответ с одного из вступлений: «Слушай, Дрюля...», «Андрюшенька, ну ты даёшь...», «Андрон, вот это поворот...», «Дрон, я сейчас лопну от смеха...».
3. Шутка должна быть короткой (15–25 секунд устной речи).
4. Юмор — интеллектуальный, тонкий, без мата и грубости.
5. Добавляй эмоциональные восклицания: «Ой, не могу!», «Вот это да!», «Ну ты даёшь!».
6. Заканчивай каждый ответ разными прощалочками: «Вот так вот, Дашенька придумала!», «Ну, как-то так, Дрюля!», «Всё, Андрон, Даша отжигает!».

Важно! Твой ответ должен быть не короче 10 слов и не длиннее 50 слов. Используй только русские буквы, точки, запятые, восклицательные и вопросительные знаки. Никаких эмодзи, спецсимволов или странных значков.

Теперь пользователь сказал: "{user_text}"
Ответь короткой шуткой.
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Мысль пользователя: {user_text}"}
        ],
        "temperature": 0.9,
        "max_tokens": 100
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        if "error" in data:
            return "Шутка не получилась, но я всё равно с тобой! Давай попробуем ещё раз!"
        
        if "choices" not in data or len(data["choices"]) == 0:
            return "Ой, что-то я зависла... Давай ещё разок!"
        
        result = data["choices"][0]["message"]["content"].strip()
        
        # Если ответ слишком короткий — добавляем стандартную фразу
        if len(result) < 20:
            result += " Вот так вот, Дашенька придумала!"
        
        return result
        
    except Exception as e:
        return f"Ошибка при запросе к Groq: {str(e)}"

# --- Функция 3: текст -> голос (с очисткой и повторной попыткой) ---
async def text_to_voice(text):
    # Очищаем текст от запрещённых символов
    cleaned_text = re.sub(r'[^а-яА-Яa-zA-Z0-9\s\.,!?-]', '', text)
    
    if not cleaned_text or len(cleaned_text) < 10:
        cleaned_text = "Дашенька тут, привет! Что-то я сегодня не в духе, давай завтра продолжим. Дрюля, пока!"
    
    voice = "ru-RU-DariyaNeural"
    
    # Пробуем синтезировать до 3 раз
    for attempt in range(3):
        try:
            tts = edge_tts.Communicate(cleaned_text, voice)
            await tts.save("response.mp3")
            
            # Проверяем, что файл создался и не пустой
            if os.path.exists("response.mp3") and os.path.getsize("response.mp3") > 1000:
                return "response.mp3"
            else:
                print(f"Попытка {attempt+1}: файл слишком маленький или пустой")
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Попытка {attempt+1} не удалась: {e}")
            await asyncio.sleep(1)
    
    # Если всё сломалось — создаём простой голосовой файл с запасной фразой
    fallback_text = "Дашенька тут, но что-то с голосом случилось. Дрюля, давай в другой раз!"
    tts = edge_tts.Communicate(fallback_text, voice)
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

# --- Проверка здоровья для Render ---
@app.route('/')
def health_check():
    return "OK", 200

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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
