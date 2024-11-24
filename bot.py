import sys
if sys.platform.startswith('win'):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
import requests
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from bs4 import BeautifulSoup  # Using BeautifulSoup for easier HTML parsing

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Flask API URLs
USER_API_URL = "http://127.0.0.1:5000/user"
AVERAGE_SPENDING_API_URL = "http://127.0.0.1:5000/average_spending_by_age"

async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /user command. Fetches user data from the Flask app
    and sends it as a formatted message in Telegram.
    Usage: /user <user_id>
    """
    if not context.args:
        await update.message.reply_text("❗ Please provide a User ID.\nUsage: `/user <user_id>`", parse_mode='Markdown')
        return

    user_id = context.args[0]

    # Validate that user_id is an integer
    if not user_id.isdigit():
        await update.message.reply_text("❗ User ID must be an integer.\nUsage: `/user <user_id>`", parse_mode='Markdown')
        return

    try:
        # Send GET request to the Flask app's /user/<user_id> endpoint
        response = requests.get(f"{USER_API_URL}/{user_id}")

        if response.status_code == 200:
            # Parse the HTML response using BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table')

            if not table:
                await update.message.reply_text("❗ User data table not found in the response.", parse_mode='Markdown')
                return

            # Extract headers
            headers = [th.text.strip().lower().replace(' ', '_') for th in table.find_all('th')]

            # Extract user data from the first (and only) row
            row = table.find('tr').find_next_sibling('tr')  # Skip header row
            if not row:
                await update.message.reply_text("❗ No user data found.", parse_mode='Markdown')
                return

            user_data = [td.text.strip() for td in row.find_all('td')]

            user_info = dict(zip(headers, user_data))

            # Format the message
            message = (
                f"📄 *User Data:*\n\n"
                f"• *ID:* `{user_info.get('user_id', 'N/A')}`\n"
                f"• *Name:* `{user_info.get('name', 'N/A')}`\n"
                f"• *E-mail:* `{user_info.get('email', 'N/A')}`\n"
                f"• *Age:* `{user_info.get('age', 'N/A')}`\n"
                f"• *Total Spending:* `${float(user_info.get('total_spending', 0)):,.2f}`"
            )

            await update.message.reply_text(message, parse_mode='Markdown')

        else:
            # Parse the error message from the HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            error_p = soup.find('p', style='color: #ff6347;')

            if error_p:
                error_message = error_p.text.strip()
            else:
                error_message = 'An unknown error occurred.'

            await update.message.reply_text(f"❌ *Error {response.status_code}:* {error_message}", parse_mode='Markdown')

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {str(e)}")
        await update.message.reply_text("❌ *Error:* Failed to connect to the Flask application.", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        await update.message.reply_text(f"❌ *Error:* An unexpected error occurred: `{str(e)}`", parse_mode='Markdown')

async def average_spending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /average_spending command.
    Fetches average spending by age group as JSON and sends it to Telegram.
    """
    try:
        # Fetch JSON data from the Flask app
        response = requests.get(f"{AVERAGE_SPENDING_API_URL}?format=json")

        if response.status_code == 200:
            average_spending = response.json()

            # Format the message
            message = "📊 *Average Spending by Age Group:*\n\n"
            for age_group, avg in average_spending.items():
                message += f"• *Age Group {age_group}:* `${avg:,.2f}`\n"

            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"❌ *Error {response.status_code}:* Failed to retrieve average spending data.",
                parse_mode='Markdown'
            )

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {str(e)}")
        await update.message.reply_text(
            "❌ *Error:* Failed to connect to the Flask application.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        await update.message.reply_text(
            f"❌ *Error:* An unexpected error occurred: `{str(e)}`",
            parse_mode='Markdown'
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /start command. Sends a welcome message to the user.
    """
    welcome_message = (
        "👋 *Welcome to the User Spending Analysis Bot!*\n\n"
        "Here are the commands you can use:\n"
        "• `/start` - Show the welcome message.\n"
        "• `/user <user_id>` - Get details of a specific user.\n"
        "• `/average_spending` - View average spending by age group.\n"
        "• `/help` - Display this help message."
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /help command. Displays all available commands with explanations.
    """
    help_message = (
        "📖 *Available Commands:*\n\n"
        "• `/start` - Show the welcome message.\n"
        "• `/user <user_id>` - Get details of a specific user.\n"
        "• `/average_spending` - View average spending by age group.\n"
        "• `/help` - Display this help message."
    )
    await update.message.reply_text(help_message, parse_mode='Markdown')

def main():
    """
    Main function to set up the Telegram bot and handlers.
    """
    # Load the Telegram bot token from environment variables
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        print("Error: Telegram bot token not set in environment variables.")
        return

    # Set up the Telegram bot with your token
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("user", user_command))
    application.add_handler(CommandHandler("average_spending", average_spending_command))
    application.add_handler(CommandHandler("help", help_command))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
