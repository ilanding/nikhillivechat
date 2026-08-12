import os
import logging
import requests
import base64
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "ilanding/niky")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
FIXED_FILE_NAME = os.environ.get("FIXED_FILE_NAME", "LiveChat.apk")


def get_github_file_sha(file_path: str):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("sha")
    return None


def upload_to_github(file_path: str, file_content: bytes, commit_message: str):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    encoded_content = base64.b64encode(file_content).decode("utf-8")
    data = {
        "message": commit_message,
        "content": encoded_content,
        "branch": GITHUB_BRANCH
    }

    existing_sha = get_github_file_sha(file_path)
    is_update = existing_sha is not None
    if is_update:
        data["sha"] = existing_sha

    response = requests.put(url, headers=headers, json=data)
    success = response.status_code in [200, 201]
    return success, is_update


# /start command
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 *Hello {user.first_name}!*\n\n"
        f"I am your *LiveChat APK Upload Bot* 🤖\n\n"
        f"📌 *How to use:*\n"
        f"• Send any `.apk` file (any name)\n"
        f"• I will save it as `{FIXED_FILE_NAME}` on GitHub\n"
        f"• Old file will be replaced, link always stays the same\n\n"
        f"📂 *Repo:* `{GITHUB_REPO}`\n"
        f"🌿 *Branch:* `{GITHUB_BRANCH}`\n\n"
        f"_Just send the APK, I'll handle the rest!_ 🚀",
        parse_mode="Markdown"
    )


# /help command
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Help Menu*\n\n"
        "📤 *How to upload an APK:*\n"
        "Just send your `.apk` file — the bot will automatically:\n"
        "  1️⃣ Download the file\n"
        "  2️⃣ Upload it to GitHub\n"
        "  3️⃣ Replace the old file\n"
        "  4️⃣ Send you the download link\n\n"
        "📌 *Commands:*\n"
        "/start — Learn about the bot\n"
        "/help — This menu\n"
        "/status — Check GitHub repo status\n\n"
        "⚠️ *Note:* Only `.apk` files are accepted",
        parse_mode="Markdown"
    )


# /status command
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Checking GitHub connection...")

    url = f"https://api.github.com/repos/{GITHUB_REPO}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        await msg.edit_text(
            f"✅ *GitHub Connected!*\n\n"
            f"📂 *Repo:* `{data['full_name']}`\n"
            f"🌿 *Branch:* `{GITHUB_BRANCH}`\n"
            f"🔒 *Private:* {'Yes' if data['private'] else 'No'}\n"
            f"💾 *Size:* {data['size']} KB\n\n"
            f"_Everything is working fine!_ 🎉",
            parse_mode="Markdown"
        )
    else:
        await msg.edit_text(
            f"❌ *GitHub Connection Failed!*\n\n"
            f"Status Code: `{response.status_code}`\n"
            f"Please check your `GITHUB_TOKEN` and `GITHUB_REPO`.",
            parse_mode="Markdown"
        )


# Document/APK handler
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name

    # Only APK allowed
    if not file_name.lower().endswith(".apk"):
        await update.message.reply_text(
            f"❌ *Invalid File!*\n\n"
            f"`{file_name}` is not accepted.\n"
            f"Please send only `.apk` files! 📦",
            parse_mode="Markdown"
        )
        return

    # Step 1: Received
    file_size_mb = round(document.file_size / (1024 * 1024), 2)
    status_msg = await update.message.reply_text(
        f"📥 *APK Received!*\n\n"
        f"📄 Original Name: `{file_name}`\n"
        f"🔄 Renaming to: `{FIXED_FILE_NAME}`\n"
        f"📦 Size: `{file_size_mb} MB`\n\n"
        f"⏳ Downloading from Telegram...",
        parse_mode="Markdown"
    )

    # Step 2: Downloading
    try:
        file = await context.bot.get_file(document.file_id)
        file_content = bytes(await file.download_as_bytearray())
    except Exception as e:
        await status_msg.edit_text(
            f"❌ *Download Failed!*\n\n"
            f"Could not download file from Telegram.\n"
            f"Error: `{str(e)}`",
            parse_mode="Markdown"
        )
        return

    # Step 3: Uploading to GitHub
    await status_msg.edit_text(
        f"📤 *Uploading to GitHub...*\n\n"
        f"📄 File: `{FIXED_FILE_NAME}`\n"
        f"📦 Size: `{file_size_mb} MB`\n"
        f"📂 Repo: `{GITHUB_REPO}`\n\n"
        f"⏳ Please wait...",
        parse_mode="Markdown"
    )

    try:
        commit_msg = f"Update {FIXED_FILE_NAME} via Telegram bot (original: {file_name})"
        success, is_update = upload_to_github(FIXED_FILE_NAME, file_content, commit_msg)
    except Exception as e:
        await status_msg.edit_text(
            f"❌ *Upload Failed!*\n\n"
            f"Could not upload to GitHub.\n"
            f"Error: `{str(e)}`",
            parse_mode="Markdown"
        )
        return

    # Step 4: Result
    if success:
        download_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{FIXED_FILE_NAME}?no-cache"
        action = "🔄 Updated" if is_update else "🆕 Uploaded"
        await status_msg.edit_text(
            f"✅ *{action} Successfully!*\n\n"
            f"📄 *Saved As:* `{FIXED_FILE_NAME}`\n"
            f"📦 *Size:* `{file_size_mb} MB`\n"
            f"📂 *Repo:* `{GITHUB_REPO}`\n\n"
            f"📥 *Direct Download Link (Permanent):*\n"
            f"`{download_url}`",
            parse_mode="Markdown"
        )
    else:
        await status_msg.edit_text(
            f"❌ *GitHub Upload Failed!*\n\n"
            f"Possible reasons:\n"
            f"• `GITHUB_TOKEN` expired or invalid\n"
            f"• Repo `{GITHUB_REPO}` does not exist\n"
            f"• File size too large (GitHub limit: 100MB)\n\n"
            f"_Use /status command to check_",
            parse_mode="Markdown"
        )


# Any other text
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📁 Please send me an `.apk` file!\n\n"
        "Type /help for available commands 👇",
        parse_mode="Markdown"
    )


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
