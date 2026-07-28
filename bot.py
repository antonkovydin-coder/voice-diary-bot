import os
import re
import time
import requests
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup

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

# --- ТВОЁ РЕЗЮМЕ ---
MY_RESUME = """
Ковыдин Андрей, 36 лет, Москва.
Senior Project Manager / Delivery Manager (Digital / Banking / IT).
Опыт 5+ лет в Т-Банке и Совкомбанке.
Управление портфелем цифровых инициатив, координация 12+ кросс-функциональных команд.
Навыки: Agile, Scrum, Kanban, Jira, управление бэклогом, фасилитация, риск-менеджмент.
Результаты: рост конверсии на 30%, запуск 100+ A/B-тестов.
"""

# --- ПАРСИНГ HEADHUNTER (С ЭМУЛЯЦИЕЙ ЧЕЛОВЕКА) ---
def get_vacancies_from_hh(query):
    url = f"https://hh.ru/search/vacancy?text={query}&area=1"
    
    # Заголовки как у обычного браузера
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    }
    
    try:
        # Имитация реального пользователя
        session = requests.Session()
        session.headers.update(headers)
        
        # Первый запрос — как человек открывает сайт
        response = session.get(url, timeout=20)
        
        if response.status_code != 200:
            send_to_telegram(f"⚠️ Ошибка доступа к HeadHunter (статус: {response.status_code})")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        vacancies = []
        
        # Ищем все блоки с вакансиями
        items = soup.find_all('div', class_='vacancy-serp-item-body')
        if not items:
            items = soup.find_all('div', class_='vacancy-serp-item')
        
        for item in items:
            # Название и ссылка
            link_tag = item.find('a', class_='bloko-link')
            if not link_tag:
                continue
            
            title = link_tag.text.strip()
            link = link_tag.get('href')
            if link and '/vacancy/' in link:
                full_link = 'https://hh.ru' + link if link.startswith('/') else link
            else:
                continue
            
            # Компания
            company_tag = item.find('a', class_='bloko-link bloko-link_kind-tertiary')
            company = company_tag.text.strip() if company_tag else "Не указана"
            
            vacancies.append({
                'title': title,
                'link': full_link,
                'company': company
            })
        
        return vacancies
        
    except Exception as e:
        send_to_telegram(f"❌ Ошибка: {str(e)}")
        return []

# --- АНАЛИЗ ВАКАНСИЙ ЧЕРЕЗ НЕЙРОСЕТЬ ---
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

# --- ОСНОВНАЯ ФУНКЦИЯ ---
def check_vacancies():
    send_to_telegram("🧠 Запускаю поиск на HeadHunter...")
    
    queries = [
        "Руководитель+проектов",
        "Project+Manager",
        "Менеджер+проектов"
    ]
    
    all_vacancies = []
    seen_links = set()
    
    for query in queries:
        vacancies = get_vacancies_from_hh(query)
        
        for vac in vacancies:
            if vac['link'] in seen_links:
                continue
            seen_links.add(vac['link'])
            all_vacancies.append(vac)
        
        time.sleep(3)  # Большая пауза между запросами
    
    if not all_vacancies:
        send_to_telegram("⚠️ Вакансии не найдены. Проверь доступ к сайту.")
        return
    
    send_to_telegram(f"📊 Найдено {len(all_vacancies)} вакансий (без дублей)")
    
    matched = []
    for vac in all_vacancies:
        vacancy_text = f"{vac['title']} {vac['company']}"
        match_percent = analyze_vacancy(vacancy_text)
        
        if match_percent >= 70:
            matched.append({
                'title': vac['title'],
                'link': vac['link'],
                'company': vac['company'],
                'match': match_percent
            })
        
        time.sleep(1)
    
    if matched:
        matched.sort(key=lambda x: x['match'], reverse=True)
        message = f"🔔 Найдено {len(matched)} вакансий (≥ 70%):\n\n"
        for item in matched:
            message += f"• {item['match']}% — {item['title']}\n"
            message += f"  {item['company']}\n"
            message += f"  {item['link']}\n\n"
        send_to_telegram(message)
    else:
        send_to_telegram("⚠️ Вакансий с совпадением ≥ 70% не найдено.")

# --- ВЕБХУК ---
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
    webhook_url = f"https://voice-diary-bot.onrender.com/{TELEGRAM_TOKEN}"
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    try:
        requests.get(set_url)
        print("✅ Webhook установлен")
    except Exception as e:
        print(f"Ошибка webhook: {e}")
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_vacancies,
        CronTrigger(day_of_week='mon-fri', hour='9-18', minute=0),
        id='vacancy_check'
    )
    scheduler.start()
    print("✅ Планировщик запущен")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
