import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ai import ask_groq, generate_image, clear_history

user_modes: dict[int, str] = {}
# Хранит ID сообщений бота для каждого пользователя
bot_messages: dict[int, list[int]] = {}


def get_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🎨 Генерация фото", callback_data="mode_image"),
            InlineKeyboardButton("📚 Помощь с ДЗ", callback_data="mode_homework"),
        ],
        [
            InlineKeyboardButton("💻 Создание кода", callback_data="mode_code"),
            InlineKeyboardButton("💬 Общение", callback_data="mode_chat"),
        ],
        [
            InlineKeyboardButton("😈 Грубое общение", callback_data="mode_rude"),
        ],
        [
            InlineKeyboardButton("🗑 Очистить историю", callback_data="clear_history"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


MODE_NAMES = {
    "image": "🎨 Генерация фото",
    "homework": "📚 Помощь с ДЗ",
    "code": "💻 Создание кода",
    "chat": "💬 Общение",
    "rude": "😈 Грубое общение",
}

MODE_HINTS = {
    "image": "Опиши, что хочешь увидеть, и я нарисую это для тебя.",
    "homework": "Напиши задачу или вопрос по учёбе — отвечу кратко и по делу.",
    "code": "Опиши задачу или скинь код — напишу или исправлю.",
    "chat": "Просто пиши, поговорим обо всём.",
    "rude": "Ну давай, пиши. Только не обижайся потом 😏",
}


async def track_message(msg, user_id: int):
    """Сохраняет ID сообщения бота."""
    if user_id not in bot_messages:
        bot_messages[user_id] = []
    bot_messages[user_id].append(msg.message_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_modes[user.id] = "chat"
    msg = await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\nЯ умный ИИ-бот. Выбери режим и начнём:",
        reply_markup=get_main_keyboard(),
    )
    await track_message(msg, user.id)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("Выбери режим:", reply_markup=get_main_keyboard())
    await track_message(msg, update.effective_user.id)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "clear_history":
        # Очищаем память бота
        mode = user_modes.get(user_id, "chat")
        clear_history(user_id, mode)

        # Удаляем все сообщения бота
        deleted = 0
        for msg_id in bot_messages.get(user_id, []):
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                deleted += 1
            except Exception:
                pass
        bot_messages[user_id] = []

        # Отправляем новое меню
        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🗑 Удалено {deleted} сообщений. История очищена.\n\nВыбери режим:",
            reply_markup=get_main_keyboard(),
        )
        bot_messages[user_id].append(msg.message_id)
        return

    mode = query.data.replace("mode_", "")
    user_modes[user_id] = mode
    await query.edit_message_text(
        f"Режим: {MODE_NAMES.get(mode)}\n\n{MODE_HINTS.get(mode)}\n\nСменить режим — /menu",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    mode = user_modes.get(user_id, "chat")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    if mode == "image":
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="upload_photo"
        )
        image_bytes = await generate_image(text)
        if image_bytes:
            buf = io.BytesIO(image_bytes)
            buf.name = "image.jpg"
            msg = await update.message.reply_photo(
                photo=buf,
                caption=f'🎨 По запросу: "{text}"',
            )
        else:
            msg = await update.message.reply_text(
                "⚠️ Не удалось сгенерировать изображение. Попробуй другой запрос."
            )
        await track_message(msg, user_id)
    else:
        reply = await ask_groq(user_id, text, mode)
        if len(reply) > 4096:
            for i in range(0, len(reply), 4096):
                msg = await update.message.reply_text(reply[i:i+4096])
                await track_message(msg, user_id)
        else:
            msg = await update.message.reply_text(reply)
            await track_message(msg, user_id)
