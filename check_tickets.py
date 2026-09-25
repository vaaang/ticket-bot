import json
import os
import sys
import requests

# ---------- НАСТРОЙКИ ----------

SITES = {
    "vivaticket": {
        "url": "https://www.vivaticket.com/it/ticket/harry-styles/315431",
        # фразы, которые означают "билетов нет". Если НИ ОДНОЙ из них
        # на странице не найдено — считаем, что билеты появились.
        "sold_out_phrases": [
            "non disponibile",
            "esaurito",
            "non sono disponibili",
            "sold out",
        ],
    },
    "ticketone": {
        "url": "https://www.ticketone.it/event/harry-styles-together-together-circo-massimo-22114624/",
        "sold_out_phrases": [
            "non disponibile",
            "esaurito",
            "sold out",
            "biglietti non disponibili",
        ],
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


def check_site(name, cfg):
    try:
        resp = requests.get(cfg["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{name}] Ошибка запроса: {e}")
        return None  # не меняем состояние, если сайт не ответил

    page_text = resp.text.lower()
    is_sold_out = any(phrase in page_text for phrase in cfg["sold_out_phrases"])
    return not is_sold_out  # True = билеты похоже есть


def main():
    state = load_state()
    changed = False

    for name, cfg in SITES.items():
        available = check_site(name, cfg)
        if available is None:
            continue

        prev = state.get(name)

        if available and prev != "available":
            send_telegram(f"🎫 Похоже, появились билеты: {name}\n{cfg['url']}")
            state[name] = "available"
            changed = True
        elif not available and prev != "sold_out":
            state[name] = "sold_out"
            changed = True
        else:
            state[name] = state.get(name, "sold_out")

    if changed:
        save_state(state)
        print("Состояние обновлено:", state)
    else:
        print("Без изменений:", state)


if __name__ == "__main__":
    main()
