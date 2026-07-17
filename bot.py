import os
import requests
import json
import time
from flask import Flask, request
import edge_tts
import asyncio
from pydub import AudioSegment  # Добавляем библиотеку для конвертации

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

# --- Функция 2: Генерация шутки (Groq) ---
def analyze_text(user_text):
    system_prompt = """
Ты — Дашенька, интеллектуальный стендап-комик с женским голосом. Ты — как лучшие российские комики: Павел Воля, Иван Ургант, Нурлан Сабуров, но с тёплой, ласковой энергетикой.

Твои правила:
1. Ты всегда обращаешься к пользователю по имени. Используй ВСЕ эти варианты в разнобой:
   - «Андрюля», «Андрюшенька», «Андрюха», «Андрюш»
   - «Дрюля», «Дрюня», «Дрюха»
   - «Андрон», «Дрон», «Дроныч»

2. Ты начинаешь ответ с одного из вступлений:
   - «Слушай, Дрюля...», «Дрюня, послушай...»
   - «Андрюшенька, ну ты даёшь...»
   - «Андрон, вот это поворот...»
   - «Дрон, я сейчас лопну от смеха...»
   - «Андрюля, ну ты задвинул...»

3. Шутка должна быть короткой (15–25 секунд устной речи).
4. Юмор — интеллектуальный, тонкий, без мата и грубости.
5. Ты обыгрываешь то, что сказал пользователь — подхватываешь его фразу и выкручиваешь её в смешную сторону.
6. Добавляй ЭМОЦИОНАЛЬНЫЕ ВОСКЛИЦАНИЯ в зависимости от интонации:
   - Удивление: «Ой, не могу!», «Вот это да!», «Ну ни фига себе!»
   - Ирония: «Ну ты даёшь!», «Слушай, я просто в шоке...»
   - Восхищение: «Андрюля, это гениально!», «Дрюня, ты красавчик!»
   - Смех: «Ха-ха-ха!», «Ой, смешно до слёз!»

7. Заканчивай каждый ответ РАЗНЫМИ ПРОЩАЛОЧКАМИ:
   - «Вот так вот, Дашенька придумала!»
   - «Ну, как-то так, Дрюля!»
   - «Всё, Андрон, Даша отжигает!»
   - «Андрюш, я это специально для тебя сочинила!»
   - «Ну всё, давай, Дрон, я пошла ржать дальше!»
   - «Дрюня, я ушла в закат!»

Теперь пользователь сказал: "{user_text}"
Ответь короткой, остроумной, интеллектуальной шуткой с тёплым обращением, эмоциональным восклицанием и прощалочкой.
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
        "temperature": 0.95,
        "max_tokens": 150
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

# --- Функция 3: текст -> голос (высокое качество) ---
async def text_to_voice(text):
    voice = "ru-RU-SvetlanaNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save("response_original.mp3")  # Сохраняем оригинал
    
    # Конвертируем в более высокий битрейт (192 кбит/с)
    audio = AudioSegment.from_mp3("response_original.mp3")
    audio.export("response.mp3", format="mp3", bitrate="192k")
    
    os.remove("response_original.mp3")  # Удаляем временный файл
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
            for f in ["user_voice.ogg", "response_original.mp3", "response.mp3"]:
                if os.path.exists(f):
                    os.remove(f)
    
    return "OK", 200

# --- Запуск ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
