from flask import Flask, jsonify, request, render_template, redirect, url_for
import sqlite3
import os
import requests
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__, template_folder='templates')
app.config['DATABASE'] = os.getenv('DATABASE_FILE', 'users_vouchers.db')

def get_db_connection():
    """
    Establish a connection to the SQLite database.
    """
    conn = sqlite3.connect(app.config['DATABASE'], uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Enables dictionary-like cursor
    return conn

def create_tables():
    """
    Create necessary tables if they don't exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create user_info table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_info (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        age INTEGER NOT NULL
    );
    """)

    # Create user_spending table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_spending (
        user_id INTEGER NOT NULL,
        money_spent REAL NOT NULL,
        year INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES user_info(user_id)
    );
    """)

    # Create high_spending_users table with bonus_points
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS high_spending_users (
        user_id INTEGER PRIMARY KEY,
        total_spending REAL NOT NULL,
        bonus_points INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES user_info(user_id)
    );
    """)

    # Create top_spending_users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS top_spending_users (
        rank INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        age INTEGER NOT NULL,
        total_spending REAL NOT NULL,
        FOREIGN KEY(user_id) REFERENCES user_info(user_id)
    );
    """)

    conn.commit()
    conn.close()
    print("Tables created successfully.")

def populate_top_spending_users():
    """
    Populate the top_spending_users table with the top 100 spenders.
    Sorting is based on total_spending descending and age ascending.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear the existing top_spending_users table
    cursor.execute("DELETE FROM top_spending_users;")

    # Query to get top 100 users
    query = """
    SELECT 
        ui.user_id, 
        ui.name, 
        ui.email, 
        ui.age, 
        SUM(us.money_spent) AS total_spending
    FROM user_info ui
    JOIN user_spending us ON ui.user_id = us.user_id
    GROUP BY ui.user_id
    ORDER BY total_spending DESC, ui.age ASC
    LIMIT 100;
    """

    top_users = cursor.execute(query).fetchall()

    # Insert top 100 users into top_spending_users with rank
    for idx, user in enumerate(top_users, start=1):
        cursor.execute("""
        INSERT INTO top_spending_users (rank, user_id, name, email, age, total_spending)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (idx, user["user_id"], user["name"], user["email"], user["age"], user["total_spending"]))

    conn.commit()
    conn.close()
    print("Top spending users populated successfully.")

def send_telegram_message(stats):
    """
    Send computed statistics to the management via Telegram.
    """
    # Load the token and chat ID from environment variables
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    # Check if TOKEN and CHAT_ID are available
    if not TOKEN or not CHAT_ID:
        print("Telegram bot token or chat ID not set in environment variables.")
        return

    # Format the message
    message = "📊 *Spending Statistics by Age Group:*\n"
    for age_group, average_spending in stats.items():
        message += f"• *Age Group {age_group}:* ${average_spending:.2f}\n"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    response = requests.post(url, data=payload)

    if response.status_code != 200:
        print(f"Failed to send message via Telegram. Status Code: {response.status_code}, Response: {response.text}")
    else:
        print("Message sent successfully via Telegram.")

def send_custom_telegram_message(message):
    """
    Send a custom message to the management via Telegram.
    """
    # Load the token and chat ID from environment variables
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    # Check if TOKEN and CHAT_ID are available
    if not TOKEN or not CHAT_ID:
        print("Telegram bot token or chat ID not set in environment variables.")
        return

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    response = requests.post(url, data=payload)

    if response.status_code != 200:
        print(f"Failed to send message via Telegram. Status Code: {response.status_code}, Response: {response.text}")
    else:
        print("Notification sent successfully via Telegram.")

# API Endpoints
@app.route("/")
def index():
    """
    Home page with four functionalities.
    """
    return render_template('index.html')

@app.route("/user/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """
    Fetch user information by user_id, including total spending.
    Render a template to display the information.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch user info
    cursor.execute("SELECT * FROM user_info WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        # Fetch total spending
        cursor.execute("""
        SELECT SUM(money_spent) as total_spending
        FROM user_spending
        WHERE user_id = ?
        """, (user_id,))
        spending = cursor.fetchone()
        total_spending = spending['total_spending'] if spending['total_spending'] else 0.0

        conn.close()

        user_data = {
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "age": user["age"],
            "total_spending": total_spending
        }

        return render_template('user.html', user=user_data)
    else:
        conn.close()
        error_message = "User not found."
        return render_template('user.html', error=error_message), 404

@app.route("/average_spending_by_age", methods=["GET"])
def average_spending_by_age():
    """
    Calculate the average spending for predefined age groups.
    Return JSON data if the 'format=json' parameter is provided, else render HTML.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT
        CASE
            WHEN age BETWEEN 18 AND 24 THEN '18-24'
            WHEN age BETWEEN 25 AND 30 THEN '25-30'
            WHEN age BETWEEN 31 AND 36 THEN '31-36'
            WHEN age BETWEEN 37 AND 47 THEN '37-47'
            ELSE '>47'
        END AS age_group,
        AVG(us.money_spent) AS average_spending
    FROM user_info ui
    JOIN user_spending us ON ui.user_id = us.user_id
    GROUP BY age_group;
    """
    results = cursor.execute(query).fetchall()
    conn.close()

    average_spending = {row["age_group"]: row["average_spending"] for row in results}

    # Return JSON if the format parameter is set
    if request.args.get("format") == "json":
        return jsonify(average_spending)

    # Render HTML template by default
    return render_template('average_spending.html', average_spending=average_spending)


@app.route("/write_high_spending_user", methods=["POST"])
def write_high_spending_user():
    """
    Add a high-spending user to the high_spending_users table and notify management.
    Users must spend at least $1,499 to qualify.
    Bonus Points:
        - 1 point for spending >= $1,499
        - 1 additional point for every $2,000 spent beyond $1,499
    """
    data = request.get_json()
    user_id = data.get("user_id")
    total_spending = data.get("total_spending")

    # Validate input
    if not user_id or not isinstance(user_id, int):
        return jsonify({"error": "Invalid user_id. It must be an integer."}), 400
    if not total_spending or not isinstance(total_spending, (int, float)):
        return jsonify({"error": "Invalid total_spending. It must be a number."}), 400

    # Check if total_spending meets the minimum requirement
    if total_spending < 1499:
        return jsonify({"error": "Total spending must be at least $1,499 to qualify as a high-spending user."}), 400

    # Calculate bonus points
    bonus_points = 1  # Base bonus point for qualifying
    additional_spending = total_spending - 1499
    additional_bonus = int(additional_spending // 2000)
    bonus_points += additional_bonus

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if user exists
        cursor.execute("SELECT name FROM user_info WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found."}), 404

        user_name = user['name']

        # Insert into high_spending_users
        cursor.execute("""
            INSERT INTO high_spending_users (user_id, total_spending, bonus_points)
            VALUES (?, ?, ?)
        """, (user_id, total_spending, bonus_points))
        conn.commit()

        # Send notification via Telegram
        message = (
            f"🛍️ *New High-Spending User Added:*\n"
            f"• *User ID:* {user_id}\n"
            f"• *Name:* {user_name}\n"
            f"• *Total Spending:* ${total_spending:.2f}\n"
            f"• *Bonus Points:* {bonus_points}"
        )
        send_custom_telegram_message(message)

        return jsonify({"message": "High spender data saved successfully.", "bonus_points": bonus_points}), 201
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({"error": "User is already a high-spending user."}), 400
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()

@app.route("/high_spending_users", methods=["GET"])
def get_high_spending_users():
    """
    Retrieve all high-spending users.
    Render a template to display the list.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = "SELECT user_id, total_spending, bonus_points FROM high_spending_users;"
        results = cursor.execute(query).fetchall()

        high_spenders = [
            {"user_id": row["user_id"], "total_spending": row["total_spending"], "bonus_points": row["bonus_points"]}
            for row in results
        ]

        conn.close()

        return render_template('high_spending_users.html', high_spenders=high_spenders)
    except sqlite3.Error as e:
        conn.close()
        error_message = f"Database error: {e}"
        return render_template('high_spending_users.html', error=error_message), 500


def calculate_bonus_points(total_spending):
    """
    Calculate bonus points based on total_spending.
    - 1 point for spending >= $1,499
    - 1 additional point for every $2,000 spent beyond $1,499
    """
    if total_spending < 1499:
        return 0
    bonus_points = 1
    additional_spending = total_spending - 1499
    additional_bonus = int(additional_spending // 2000)
    bonus_points += additional_bonus
    return bonus_points

@app.route("/top_spending_users", methods=["GET"])
def top_spending_users():
    """
    Display the top 100 spending users in a styled table, including bonus points.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
        SELECT rank, user_id, name, email, age, total_spending
        FROM top_spending_users
        ORDER BY rank ASC;
        """
        top_users = cursor.execute(query).fetchall()
        conn.close()

        # Convert Row objects to dictionaries and calculate bonus points
        top_users = [
            {
                "rank": row["rank"],
                "user_id": row["user_id"],
                "name": row["name"],
                "email": row["email"],
                "age": row["age"],
                "total_spending": row["total_spending"],
                "bonus_points": calculate_bonus_points(row["total_spending"])
            }
            for row in top_users
        ]

        return render_template('top_spending_users.html', top_users=top_users)
    except sqlite3.Error as e:
        conn.close()
        error_message = f"Database error: {e}"
        return render_template('top_spending_users.html', error=error_message), 500


if __name__ == "__main__":
    create_tables()  # Create tables if not already existing
    app.run(debug=True)
