import json
import os
import sys
import requests
from playwright.sync_api import sync_playwright

# ---------- НАСТРОЙКИ ----------

# Категории, которые нужно отслеживать на каждой странице.
# Скрипт ищет название категории на странице и смотрит, есть ли
# рядом с ним фраза "недоступно". Если нет — считает, что билет появился.
CATEGORIES = [
    "Circle PIT",
    "Disco PIT",
    "Kiss PIT",
    "Square PIT",
    "Front Standing",
]

# Сколько символов после названия категории проверять на "недоступно"
WINDOW = 400

SOLD_OUT_PHRASES = [
    "non disponibile",
    "esaurito",
    "sold out",
    "non disponibili",
]

SITES = {
    "ticketone_7ago": {
        "url": "https://www.ticketone.it/event/harry-styles-together-together-circo-massimo-22114624/",
    },
    "ticketone_8ago": {
        "url": "https://www.ticketone.it/event/harry-styles-together-together-circo-massimo-22109735/",
    },
    "vivaticket_7ago": {
        "url": "https://shop.vivaticket.com/it/sell/?cmd=prices&pcode=14272407&tcode=vt0022939",
    },
    "vivaticket_8ago": {
        "url": "https://shop.vivaticket.com/it/sell/?cmd=prices&pcode=14272408&tcode=vt0022939",
    },
}

STATE_FILE = "state.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

# ---------- ЛОГИКА ----------


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram не настроен, пропускаю отправку:", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)


def check_category(page_text_lower, category):
    """Возвращает True, если категория похожа на доступную."""
    cat_lower = category.lower()
    idx = page_text_lower.find(cat_lower)
    if idx == -1:
        return None  # категория вообще не найдена на странице
    window = page_text_lower[idx : idx + len(cat_lower) + WINDOW]
    is_sold_out = any(phrase in window for phrase in SOLD_OUT_PHRASES)
    return not is_sold_out


def fetch_rendered_html(browser, url):
    page = browser.new_page(
        user_agent=HEADERS["User-Agent"],
        locale="it-IT",
    )
    try:
        page.goto(url, timeout=30000, wait_until="networkidle")
        # небольшая доп. пауза на случай, если категории подгружаются
        # чуть позже основного контента
        page.wait_for_timeout(2000)
        html = page.content()
    finally:
        page.close()
    return html


def check_site(browser, name, cfg):
    try:
        html = fetch_rendered_html(browser, cfg["url"])
    except Exception as e:
        print(f"[{name}] Ошибка загрузки страницы: {e}")
        return {}

    page_text = html.lower()
    results = {}
    for category in CATEGORIES:
        results[category] = check_category(page_text, category)
    return results


def main():
    state = load_state()
    changed = False

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for name, cfg in SITES.items():
            results = check_site(browser, name, cfg)
            site_state = state.get(name, {})

            for category, available in results.items():
                if available is None:
                    continue  # категории нет на странице, пропускаем

                prev = site_state.get(category)

                if available and prev != "available":
                    send_telegram(
                        f"🎫 Появился билет!\n{name}: {category}\n{cfg['url']}"
                    )
                    site_state[category] = "available"
                    changed = True
                elif not available and prev != "sold_out":
                    site_state[category] = "sold_out"
                    changed = True

            state[name] = site_state

        browser.close()

    if changed:
        save_state(state)
        print("Состояние обновлено:", state)
    else:
        print("Без изменений:", state)


if __name__ == "__main__":
    main()
