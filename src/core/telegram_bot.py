
import httpx
import logging
from ..config import TELE_TOKEN, TELE_ID

logger = logging.getLogger("TelegramBot")

async def send_telegram_message(message: str):
    if not TELE_TOKEN or not TELE_ID:
        logger.warning("Telegram Config Missing (TELE_ID or TELE_TOKEN not set)")
        return
    
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELE_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            if response.status_code != 200:
                logger.error(f"Telegram Send Failed: {response.text}")
        except Exception as e:
            logger.error(f"Telegram Error: {e}")
