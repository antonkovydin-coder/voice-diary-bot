import os
import re
import time
import requests
import sqlite3
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup

# =============================================
# 1. ТВОИ КЛЮЧИ И НАСТРОЙКИ
# =============================================
TELEGRAM_TOKEN = "8910688691:AAEt7RPn5scALEy7zJkXwra3sFS5dk70irI"
GROQ_API_KEY = "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"
MY_CHAT_ID = "947067613"
# =============================================

app = Flask(__name__)

# --- ФУНКЦИЯ ДЛЯ ОТПРАВКИ СООБЩЕНИЙ В TELEGRAM (С ТОБОЙ) ---
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

# --- ТВОЕ ПОЛНОЕ РЕЗЮМЕ (ПОЛНАЯ ВЕРСИЯ) ---
MY_RESUME = """
Ковыдин Андрей, 36 лет, Москва.
Senior Project Manager / Delivery Manager (Digital / Banking / IT).

КЛЮЧЕВЫЕ НАВЫКИ И ЭКСПЕРТИЗА:
1. Управление проектами и портфелями (Agile/Scrum/Kanban/Waterfall).
2. Delivery Management: координация 12+ кросс-функциональных команд (40+ специалистов).
3. Управление бэклогом и приоритизация (Jira, YouTrack).
4. Стратегическое и квартальное планирование.
5. Стейкхолдер-менеджмент и фасилитация.
6. Риск-менеджмент, управление зависимостями.
7. Внедрение операционных моделей.
8. Управление бюджетом и ресурсами.
9. A/B-тестирование, работа с продуктовыми метриками (конверсия).
10. Customer Journey Mapping и продуктовый дизайн.
11. Работа с AI-инструментами и LLM.

ОПЫТ РАБОТЫ (5 лет 3 месяца):
1. Т-Банк (10.2025 – 01.2026) — Senior PM / Delivery Manager:
   - Управлял 3 цифровыми продуктами (соцсервисы).
   - Координировал 5 ресурсных команд (Frontend, 2 Backend, Design, PA).
   - Выстроил единый процесс оценки и приоритизации.

2. Совкомбанк (02.2022 – 07.2025) — Lead PM / Руководитель проектного направления:
   - Руководил 4 PM + Content Manager.
   - Управлял цифровыми инициативами для web-экосистемы (карты, кредиты, вклады, ипотека).
   - Координировал 12+ команд, 40+ специалистов.
   - Обеспечил реализацию 50+ инициатив в год.
   - Рост конверсии: +30%, +25%, +20%.
   - Запустил 100+ A/B-тестов.

3. Студия Graphene (09.2020 – 01.2022) — Project Manager:
   - Управлял 4+ проектами (порталы, образовательные платформы).
   - Внедрил мониторинг задач, снизив просрочки.

ОБРАЗОВАНИЕ:
Ульяновский государственный университет (2016).

ДОПОЛНИТЕЛЬНО:
- Опыт управления бюджетом.
- Опыт работы с AI-инструментами (LLM).
- Готов к гибридному формату и удаленной работе.
"""

# --- НАСТРОЙКИ ПОИСКА ---
KEYWORDS = [
    "Project Manager", "Руководитель проектов", "Проджект-менеджер", 
    "PM", "Менеджер проектов", "Delivery Manager"
]

# --- АГРЕГАТОРЫ ДЛЯ ПОИСКА (С РАЗНЫМИ ССЫЛКАМИ) ---
SOURCES = [
    {"name": "HeadHunter", "url": "https://hh.ru/search/vacancy?text=Project+Manager&area=1&search_period=1"},
    {"name": "Dream Job", "url": "https://dreamjob.ru/vacancies?keywords=Project+Manager"},
    {"name": "SuperJob", "url": "https://www.superjob.ru/vacancy/search/?keywords=Project+Manager"},
    {"name": "Работа.ру", "url": "https://www.rabota.ru/vacancy/?query=Project+Manager"},
]

# --- ПАРСЕРЫ ДЛЯ КАЖДОГО АГРЕГАТОРА (С ПОДРОБНЫМИ ОТЧЁТАМИ) ---
def parse_hh(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for item in soup.find_all('a', class_='serp-item__title'):
            href = item.get('href')
            if href:
                full_link = 'https://hh.ru' + href if href.startswith('/') else href
                links.append(full_link)
        send_to_telegram(f"✅ HeadHunter: найдено {len(links)} вакансий.")
        return links
    except Exception as e:
        send_to_telegram(f"❌ Ошибка HeadHunter: {str(e)}")
        return []

def parse_dreamjob(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'vacancy' in href and 'dreamjob' in href:
                full_link = href if href.startswith('http') else 'https://dreamjob.ru' + href
                links.append(full_link)
        send_to_telegram(f"✅ DreamJob: найдено {len(links)} вакансий.")
        return links
    except Exception as e:
        send_to_telegram(f"❌ Ошибка DreamJob: {str(e)}")
        return []

def parse_superjob(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/vacancy/' in href:
                full_link = 'https://www.superjob.ru' + href if href.startswith('/') else href
                links.append(full_link)
        send_to_telegram(f"✅ SuperJob: найдено {len(links)} вакансий.")
        return links
    except Exception as e:
        send_to_telegram(f"❌ Ошибка SuperJob: {str(e)}")
        return []

def parse_rabota_ru(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/vacancy/' in href:
                full_link = 'https://www.rabota.ru' + href if href.startswith('/') else href
                links.append(full_link)
        send_to_telegram(f"✅ Работа.ру: найдено {len(links)} вакансий.")
        return links
    except Exception as e:
        send_to_telegram(f"❌ Ошибка Работа.ру: {str(e)}")
        return []

# --- СБОР ВСЕХ ССЫЛОК С АГРЕГАТОРОВ ---
def get_all_links():
    all_links = []
    
    for source in SOURCES:
        send_to_telegram(f"🔍 Проверяю {source['name']}...")
        if source['name'] == "HeadHunter":
            links = parse_hh(source['url'])
        elif source['name'] == "Dream Job":
            links = parse_dreamjob(source['url'])
        elif source['name'] == "SuperJob":
            links = parse_superjob(source['url'])
        elif source['name'] == "Работа.ру":
            links = parse_rabota_ru(source['url'])
        else:
            links = []
        
        all_links.extend(links)
        time.sleep(2)
    
    all_links = list(set(all_links))
    send_to_telegram(f"📊 Всего найдено уникальных ссылок: {len(all_links)}.")
    return all_links

# --- ИНТЕЛЛЕКТУАЛЬНЫЙ АНАЛИЗ ВАКАНСИИ (Groq) ---
def analyze_vacancy(vacancy_text):
    prompt = f"""
Ты — эксперт по подбору персонала в IT и банковском секторе.
Оцени соответствие кандидата (резюме) и вакансии.

### РЕЗЮМЕ:
{MY_RESUME}

### ТЕКСТ ВАКАНСИИ:
{vacancy_text}

Оцени по 5 критериям: опыт, навыки, достижения, стек, soft skills.
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
        send_to_telegram(f"❌ Ошибка AI-анализа: {str(e)}")
        return 0

# --- БАЗА ДАННЫХ (ДЛЯ ЗАЩИТЫ ОТ ДУБЛЕЙ) ---
def is_new(link, db_path='vacancies.db'):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS sent (link TEXT PRIMARY KEY)')
    c.execute('SELECT * FROM sent WHERE link=?', (link,))
    result = c.fetchone()
    conn.close()
    return result is None

def mark_as_sent(link, db_path='vacancies.db'):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('INSERT INTO sent (link) VALUES (?)', (link,))
    conn.commit()
    conn.close()

# --- ОСНОВНАЯ ФУНКЦИЯ ПРОВЕРКИ (С ПОДРОБНЫМ ОТЧЁТОМ) ---
def check_vacancies():
    send_to_telegram("🧠 Запускаю интеллектуальный поиск...")
    
    # 1. Собираем ссылки
    all_links = get_all_links()
    
    if not all_links:
        send_to_telegram("⚠️ Не найдено ни одной вакансии на агрегаторах. Проверьте ссылки или работу парсеров.")
        return
    
    # 2. Анализируем каждую новую вакансию
    matched_vacancies = []
    for index, link in enumerate(all_links, 1):
        if not is_new(link):
            continue
        
        send_to_telegram(f"🔎 Анализирую вакансию {index}/{len(all_links)}...")
        
        # Здесь можно добавить загрузку текста вакансии по ссылке
        vacancy_text = "Project Manager in Banking, Agile, Jira, управление проектами, банковский сектор."
        match_percent = analyze_vacancy(vacancy_text)
        
        if match_percent >= 75:
            matched_vacancies.append((link, match_percent))
            mark_as_sent(link)
            send_to_telegram(f"✅ Совпадение {match_percent}%: {link}")
        else:
            send_to_telegram(f"⏭️ Совпадение {match_percent}% — пропускаем")
    
    # 3. Отправляем итоговый результат
    if matched_vacancies:
        message = f"🔔 Найдено {len(matched_vacancies)} подходящих вакансий:\n\n"
        for link, percent in matched_vacancies:
            message += f"• {percent}% совпадение:\n{link}\n\n"
        send_to_telegram(message)
    else:
        send_to_telegram("⚠️ Подходящих вакансий не найдено.")

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
