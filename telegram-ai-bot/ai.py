import urllib.parse
import json
import httpx
from groq import AsyncGroq
from config import GROQ_API_KEY, STABILITY_API_KEY, PROMPTS

client = AsyncGroq(api_key=GROQ_API_KEY)

# История сообщений: {user_id: [{"role": ..., "content": ...}]}
chat_history: dict[int, list] = {}
MAX_HISTORY = 20  # максимум сообщений в истории


def get_history(user_id: int, mode: str) -> list:
    return chat_history.get(f"{user_id}_{mode}", [])


def add_to_history(user_id: int, mode: str, role: str, content: str):
    key = f"{user_id}_{mode}"
    if key not in chat_history:
        chat_history[key] = []
    chat_history[key].append({"role": role, "content": content})
    # Обрезаем историю чтобы не переполнять контекст
    if len(chat_history[key]) > MAX_HISTORY:
        chat_history[key] = chat_history[key][-MAX_HISTORY:]


def clear_history(user_id: int, mode: str):
    key = f"{user_id}_{mode}"
    chat_history.pop(key, None)


async def ask_groq(user_id: int, user_message: str, mode: str = "chat") -> str:
    system_prompt = PROMPTS.get(mode, PROMPTS["chat"])
    add_to_history(user_id, mode, "user", user_message)
    history = get_history(user_id, mode)
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}] + history,
            max_tokens=2048,
            temperature=0.8,
        )
        reply = response.choices[0].message.content
        add_to_history(user_id, mode, "assistant", reply)
        return reply
    except Exception as e:
        # Убираем последнее сообщение из истории если запрос упал
        key = f"{user_id}_{mode}"
        if chat_history.get(key):
            chat_history[key].pop()
        return f"Ошибка: {e}"


async def generate_image(prompt: str) -> bytes | None:
    """Генерирует изображение через Stability AI."""
    url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Accept": "image/*",
    }
    try:
        async with httpx.AsyncClient(timeout=120) as http:
            r = await http.post(url, headers=headers, files={
                "prompt": (None, prompt),
                "output_format": (None, "jpeg"),
            })
            print(f"Stability status: {r.status_code}, size: {len(r.content)}")
            if r.status_code == 200 and len(r.content) > 1000:
                return r.content
            else:
                print(f"Stability error: {r.text}")
    except Exception as e:
        print(f"Stability error: {e}")
    return None
