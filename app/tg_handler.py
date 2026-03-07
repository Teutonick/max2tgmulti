import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.account_manager import AccountManager

log = logging.getLogger(__name__)

PENDING_REPLY_CHAT_KEY = "pending_reply_chat_id"
PENDING_REPLY_LABEL_KEY = "pending_reply_label"
PENDING_REPLY_ACCOUNT_KEY = "pending_reply_account_id"


async def _on_start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "/register <device_id> <token> [name] - добавить MAX аккаунт\n"
        "/accounts - список ваших MAX аккаунтов\n"
        "/remove <account_id> - отключить MAX аккаунт\n"
        "/cancel - отменить текущий reply"
    )


async def _on_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    manager: AccountManager = context.bot_data["account_manager"]
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Формат: /register <device_id> <token> [name]"
        )
        return

    device_id = args[0].strip()
    token = args[1].strip()
    title = " ".join(args[2:]).strip()
    tg_user_id = int(update.effective_user.id)

    record = await manager.add_account(
        tg_user_id=tg_user_id,
        max_token=token,
        max_device_id=device_id,
        title=title,
    )
    label = record.title or f"MAX #{record.id}"
    await update.message.reply_text(f"✅ Аккаунт добавлен: {label} (ID={record.id})")


async def _on_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    manager: AccountManager = context.bot_data["account_manager"]
    tg_user_id = int(update.effective_user.id)
    accounts = await manager.list_accounts_for_user(tg_user_id)

    if not accounts:
        await update.message.reply_text("У вас пока нет зарегистрированных MAX аккаунтов.")
        return

    rows = ["Ваши MAX аккаунты:"]
    for acc in accounts:
        label = acc.title or f"MAX #{acc.id}"
        rows.append(f"- ID={acc.id}: {label}")
    await update.message.reply_text("\n".join(rows))


async def _on_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    manager: AccountManager = context.bot_data["account_manager"]
    args = context.args or []
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Формат: /remove <account_id>")
        return

    account_id = int(args[0])
    tg_user_id = int(update.effective_user.id)
    ok = await manager.remove_account(account_id, tg_user_id)
    if ok:
        await update.message.reply_text(f"✅ Аккаунт {account_id} отключен.")
    else:
        await update.message.reply_text("⚠️ Аккаунт не найден или недоступен.")


async def _on_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] != "reply":
        return

    account_id_str, chat_id_str = parts[1], parts[2]
    if not account_id_str.isdigit():
        await query.message.reply_text("⚠️ Некорректный account_id.")
        return

    account_id = int(account_id_str)
    try:
        max_chat_id = int(chat_id_str)
    except ValueError:
        max_chat_id = chat_id_str

    context.user_data[PENDING_REPLY_ACCOUNT_KEY] = account_id
    context.user_data[PENDING_REPLY_CHAT_KEY] = max_chat_id

    source_text = query.message.text or query.message.caption or ""
    label = source_text.split("\n")[0] if source_text else str(max_chat_id)
    context.user_data[PENDING_REPLY_LABEL_KEY] = label

    await query.message.reply_text(
        f"✏️ Напишите ответ для <b>{label}</b>:\n"
        "<i>(или /cancel для отмены)</i>",
        parse_mode="HTML",
    )


async def _on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.pop(PENDING_REPLY_CHAT_KEY, None) is not None:
        context.user_data.pop(PENDING_REPLY_LABEL_KEY, None)
        context.user_data.pop(PENDING_REPLY_ACCOUNT_KEY, None)
        await update.message.reply_text("❌ Ответ отменен.")
    else:
        await update.message.reply_text("Нет активного ответа для отмены.")


async def _on_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    account_id = context.user_data.pop(PENDING_REPLY_ACCOUNT_KEY, None)
    max_chat_id = context.user_data.pop(PENDING_REPLY_CHAT_KEY, None)
    label = context.user_data.pop(PENDING_REPLY_LABEL_KEY, None)
    if account_id is None or max_chat_id is None:
        return

    manager: AccountManager = context.bot_data["account_manager"]
    tg_user_id = int(update.effective_user.id)
    text = update.message.text
    try:
        ok = await manager.send_message(account_id, tg_user_id, max_chat_id, text)
        if ok:
            await update.message.reply_text(
                f"✅ Отправлено -> <b>{label or max_chat_id}</b>",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "⚠️ Не удалось отправить (аккаунт недоступен или нет прав)."
            )
    except Exception:
        log.exception("Failed to send reply for account=%s chat=%s", account_id, max_chat_id)
        await update.message.reply_text("⚠️ Ошибка при отправке в Max.")


def build_tg_app(token: str, account_manager: AccountManager) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["account_manager"] = account_manager

    private_filter = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", _on_start, filters=private_filter))
    app.add_handler(CommandHandler("register", _on_register, filters=private_filter))
    app.add_handler(CommandHandler("accounts", _on_accounts, filters=private_filter))
    app.add_handler(CommandHandler("remove", _on_remove, filters=private_filter))
    app.add_handler(CommandHandler("cancel", _on_cancel, filters=private_filter))
    app.add_handler(CallbackQueryHandler(_on_reply_button, pattern=r"^reply:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & private_filter, _on_text_reply))
    return app
