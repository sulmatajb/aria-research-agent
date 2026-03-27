#!/usr/bin/env python3
"""ARIA Telegram Bot — Besnik's window into the research agent system."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import db
import config

db.init()

ICONS = {
    'pending':     '⏳',
    'in_progress': '🔄',
    'done':        '✅',
    'failed':      '❌',
    'assigned':    '📌',
}

TYPE_LABELS = {
    'user_request': '📩 request',
    'search':       '🔍 search',
    'scrape':       '🕷 scrape',
    'synthesize':   '✍️ synthesis',
    'zotero_add':   '📚 zotero',
    'telegram_response': '📱 response',
}


def task_line(t):
    icon = ICONS.get(t['status'], '•')
    label = TYPE_LABELS.get(t['type'], t['type'])
    payload = t['payload']
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    desc = (payload.get('query') or payload.get('url') or
            payload.get('message') or payload.get('objective') or '')
    desc = str(desc)[:55]
    return f"{icon} \\[\\#{t['id']}\\] {label} — {_esc(desc)}"


def _esc(text):
    """Escape MarkdownV2 special chars."""
    for ch in r'_*[]()~`>#+-=|{}.!\\':
        text = text.replace(ch, f'\\{ch}')
    return text


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.save_kv('telegram_chat_id', chat_id)
    await update.message.reply_text(
        "🤖 *ARIA online\\.*\n\n"
        "I'm your dissertation research supervisor\\. Send me a task and I'll coordinate the team\\.\n\n"
        "*/status* — task dashboard\n"
        "*/help* — example commands\n\n"
        "Or just type your research request\\.",
        parse_mode='MarkdownV2'
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*ARIA — example requests*\n\n"
        "• Find papers on LLM agents for home energy management\n"
        "• Find a replacement for the Marzbali 2017 citation\n"
        "• Verify the authors of arXiv:2510\\.26603\n"
        "• Search for FERC Order 2222 demand response literature\n"
        "• Find the Lissa 2025 survey on LLMs in building energy\n"
        "• Scrape and verify https://arxiv\\.org/abs/2602\\.15219",
        parse_mode='MarkdownV2'
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_recent_tasks(20)
    visible = [t for t in tasks if t['type'] != 'telegram_response']

    active    = [t for t in visible if t['status'] in ('pending', 'in_progress')]
    completed = [t for t in visible if t['status'] == 'done'][:6]
    failed    = [t for t in visible if t['status'] == 'failed'][:3]

    lines = ["📊 *ARIA Status*\n"]

    if active:
        lines.append("*Active:*")
        lines += [task_line(t) for t in active[:8]]
    if completed:
        lines.append("\n*Completed:*")
        lines += [task_line(t) for t in completed]
    if failed:
        lines.append("\n*Failed:*")
        lines += [task_line(t) for t in failed]
    if not visible:
        lines.append("_No tasks yet\\. Send me a research request\\._")

    await update.message.reply_text('\n'.join(lines), parse_mode='MarkdownV2')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    db.save_kv('telegram_chat_id', chat_id)

    task_id = db.create_task(
        'user_request',
        {'message': text},
        assigned_to='supervisor',
        chat_id=chat_id
    )
    db.log('telegram', f"Task #{task_id} from user: {text[:80]}")

    escaped_id = _esc(str(task_id))
    await update.message.reply_text(
        f"📋 Task \\#{escaped_id} queued\\. ARIA is on it\\.",
        parse_mode='MarkdownV2'
    )


async def poll_responses(context: ContextTypes.DEFAULT_TYPE):
    """Poll DB for responses from the Supervisor and send to Telegram."""
    for resp in db.get_pending_telegram_responses():
        try:
            payload = resp['payload']
            if isinstance(payload, str):
                payload = json.loads(payload)
            chat_id = payload.get('chat_id') or db.get_kv('telegram_chat_id')
            if chat_id:
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=payload.get('message', ''),
                    parse_mode='Markdown'
                )
            db.update_task(resp['id'], status='done')
        except Exception as e:
            db.log('telegram', f"Send failed: {e}", level='error')


def main():
    db.log('telegram', "ARIA Telegram bot starting")
    print("📱 ARIA Telegram Bot running. Ctrl+C to stop.\n")

    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.job_queue.run_repeating(poll_responses, interval=5, first=5)
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
