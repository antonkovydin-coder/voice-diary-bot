import os
import re
import time
import requests
import feedparser
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# =============================================
# 1. ТВОИ КЛЮЧИ
# =============================================
TELEGRAM_TOKEN = "8910688691:AAEt7RPn5scALEy7zJkXwra3sFS5dk70irI"
GROQ_API_KEY = "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"
MY_CHAT_ID = "947067613"
# =============================================

app = Flask(__name__)

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

# --- ТВОЁ РЕЗЮМЕ (НЕЙРОСЕТЬ БУДЕТ СРАВНИВАТЬ С НИМ) ---
MY_RESUME = """
Ковыдин Андрей, 36 лет, Москва.
Senior Project Manager / Delivery Manager (Digital / Banking / IT).
Опыт 5+ лет в Т-Банке и Совкомбанке.
Управление портфелем цифровых инициатив, координация 12+ кросс-функциональных команд.
Навыки: Agile, Scrum, Kanban, Jira, управление бэклогом, фасилитация, риск-менеджмент.
Результаты: рост конверсии на 30%, запуск 100+ A/B-тестов.
"""

# --- ФУНКЦИЯ: СОБИРАЕМ ВСЕ ВАКАНСИИ С HEADHUNTER (RSS) ---
def get_all_vacancies():
    queries = [
        "Руководитель+проектов",
        "Project+Manager",
        "Менеджер+проектов"
    ]
    
    all_vacancies = []
    seen_links = set()
    
    for query in queries:
        rss_url = f"https://hh.ru/rss/search/vacancy?text={query}&area=1&search_period=3"
        try:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                continue
            
            for entry in feed.entries:
                link = entry.link
                if link in seen_links:
                    continue  # Пропускаем дубли в рамках одного поиска
                seen_links.add(link)
                
                title = entry.title
                summary = entry.summary if hasattr(entry, 'summary') else ""
                company = "Не указана"
                if "в" in title:
                    parts = title.split("в")
                    if len(parts) > 1:
                        company = parts[-1].strip()
                
                all_vacancies.append({
                    'title': title,
                    'link': link,
                    'company': company,
                    'summary': summary
                })
            time.sleep(1)  # Пауза между запросами
        except Exception as e:
            send_to_telegram(f"⚠️ Ошибка при запросе '{query}': {str(e)}")
    
    send_to_telegram(f"📊 Найдено вакансий (без дублей): {len(all_vacancies)}")
    return all_vacancies

# --- ФУНКЦИЯ: АНАЛИЗ ЧЕРЕЗ НЕЙРОСЕТЬ (GROQ) ---
def analyze_vacancy(vacancy_text):
    prompt = f"""
Ты — эксперт по подбору персонала в IT и банковском секторе.
Оцени соответствие кандидата и вакансии в процентах.

Резюме кандидата:
{MY_RESUME}

Текст вакансии:
{vacancy_text}

Ответь строго в формате: "Совпадение: X%", где X — число от 0 до 100.
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 30
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            result = data["choices"][0]["message"]["content"]
            numbers = re.findall(r'\d+', result)
            if numbers:
                return int(numbers[0])
        return 0
    except Exception as e:
        return 0

# --- ГЛАВНАЯ ФУНКЦИЯ: ПРОВЕРКА И ОТПРАВКА ---
def check_vacancies():
    send_to_telegram("🧠 Запускаю сканирование HeadHunter...")
    
    # 1. Получаем все вакансии
    vacancies = get_all_vacancies()
    if not vacancies:
        send_to_telegram("⚠️ Вакансии не найдены. Проверь подключение.")
        return
    
    # 2. Анализируем каждую
    matched = []
    total = len(vacancies)
    
    for idx, vac in enumerate(vacancies, 1):
        vacancy_text = f"{vac['title']} {vac['company']} {vac['summary']}"
        match_percent = analyze_vacancy(vacancy_text)
        
        if match_percent >= 70:
            matched.append({
                'title': vac['title'],
                'link': vac['link'],
                'company': vac['company'],
                'match': match_percent
            })
        
        # Отправляем статус каждые 10 вакансий
        if idx % 10 == 0:
            send_to_telegram(f"⏳ Обработано {idx} из {total} вакансий...")
        
        time.sleep(0.5)  # Пауза, чтобы не перегружать API
    
    # 3. Сортируем и отправляем результат
    if matched:
        matched.sort(key=lambda x: x['match'], reverse=True)
        message = f"🔔 Найдено {len(matched)} вакансий с совпадением ≥ 70%:\n\n"
        for item in matched:
            message += f"• {item['match']}% — {item['title']}\n"
            message += f"  {item['company']}\n"
            message += f"  {item['link']}\n\n"
        send_to_telegram(message)
    else:
        send_to_telegram("⚠️ Не найдено вакансий с совпадением 70% и выше.")

# --- ВЕБХУК ДЛЯ TELEGRAM ---
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        text = update["message"]["text"]
        if text in ["1", "/check", "проверь"]:
            check_vacancies()
        else:
            send_to_telegram("ℹ️ Отправьте '1' для поиска вакансий.")
    return "OK", 200

# --- ЗАПУСК ---
if __name__ == "__main__":
    # Установка вебхука
    webhook_url = f"https://voice-diary-bot.onrender.com/{TELEGRAM_TOKEN}"
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    try:
        requests.get(set_url)
        print("✅ Webhook установлен")
    except Exception as e:
        print(f"Ошибка webhook: {e}")
    
    # Планировщик (каждый час с 9 до 18 в будни)
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_vacancies,
        CronTrigger(day_of_week='mon-fri', hour='9-18', minute=0),
        id='vacancy_check'
    )
    scheduler.start()
    print("✅ Планировщик запущен")
    
    # Запуск Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
