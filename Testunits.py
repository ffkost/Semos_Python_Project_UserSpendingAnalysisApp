import pytest, os, tempfile, sqlite3

from proektot4 import app, get_db_connection, create_tables

@pytest.fixture
def client():
    """Test fixture that provides the Flask test client and initializes the database."""
    app.config['TESTING'] = True
    fd, db_path = tempfile.mkstemp()  # Create a temporary file and get the file descriptor and path
    os.close(fd)  # Close the file descriptor
    app.config['DATABASE'] = db_path  # Use the temporary file as the database

    try:
        with app.test_client() as client:
            with app.app_context():
                create_tables()  # Create tables in the temporary database

                # Initialize the database with test data
                conn = get_db_connection()
                cursor = conn.cursor()

                # Insert test data into user_info
                cursor.execute(
                    "INSERT INTO user_info (user_id, name, email, age) VALUES (?, ?, ?, ?)",
                    (90, 'John Doe', 'john@example.com', 25)
                )
                cursor.execute(
                    "INSERT INTO user_info (user_id, name, email, age) VALUES (?, ?, ?, ?)",
                    (91, 'Jane Smith', 'jane@example.com', 30)
                )
                cursor.execute(
                    "INSERT INTO user_info (user_id, name, email, age) VALUES (?, ?, ?, ?)",
                    (92, 'Bob Johnson', 'bob@example.com', 35)
                )
                cursor.execute(
                    "INSERT INTO user_info (user_id, name, email, age) VALUES (?, ?, ?, ?)",
                    (93, 'Alice Brown', 'alice@example.com', 50)
                )

                # Insert test data into user_spending
                cursor.executemany(
                    "INSERT INTO user_spending (user_id, money_spent, year) VALUES (?, ?, ?)",
                    [
                        (90, 100.0, 2021),
                        (90, 150.0, 2022),
                        (91, 200.0, 2022),
                        (92, 300.0, 2022),
                        (93, 400.0, 2022),
                    ]
                )

                conn.commit()
                conn.close()

            yield client  # This will run the tests
    finally:
        os.unlink(db_path)  # Delete the temporary database file after tests are done

def test_total_spent(client):
    """Tests the total spending for a user via the /user/<user_id> endpoint."""
    response = client.get('/user/90')
    assert response.status_code == 200
    # Check that '250.0' is present in the HTML response
    assert b'250.0' in response.data  # Adjust based on your template's actual rendering

def test_average_spending_by_age(client):
    """Tests the /average_spending_by_age endpoint."""
    response = client.get('/average_spending_by_age')
    assert response.status_code == 200
    # Check that the average spendings are present in the HTML response
    assert b'150.0' in response.data  # For age group 25-30
    assert b'300.0' in response.data  # For age group 31-36
    assert b'400.0' in response.data  # For age group >47

def test_high_spending_users(client):
    """Tests the /high_spending_users endpoint."""
    # Insert a high spender into the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO high_spending_users (user_id, total_spending, bonus_points)
        VALUES (?, ?, ?)
    """, (90, 2500.0, 2))
    conn.commit()
    conn.close()

    # Test retrieving high spenders
    response = client.get('/high_spending_users')
    assert response.status_code == 200
    # Check that the high spender is displayed
    assert b'2500.0' in response.data
    assert b'2' in response.data  # Bonus points


def test_invalid_high_spending_user(client):
    """Tests invalid input handling for /write_high_spending_user."""
    # Test with insufficient spending
    payload = {'user_id': 90, 'total_spending': 1000.0}
    response = client.post('/write_high_spending_user', json=payload)
    assert response.status_code == 400
    assert b"Total spending must be at least $1,499" in response.data

    # Test with non-existent user
    payload = {'user_id': 99, 'total_spending': 2000.0}
    response = client.post('/write_high_spending_user', json=payload)
    assert response.status_code == 404
    assert b"User not found" in response.data

def test_add_high_spending_user(client):
    """Tests the /write_high_spending_user POST endpoint."""
    payload = {'user_id': 90, 'total_spending': 2500.0}  # Ensure total_spending >= 1499
    response = client.post('/write_high_spending_user', json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data['message'] == 'High spender data saved successfully.'
    # Calculate expected bonus points
    expected_bonus = 1 + ((2500 - 1499) // 2000)
    assert data['bonus_points'] == expected_bonus

    # Verify that the user is added to high_spending_users via database query
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, total_spending, bonus_points FROM high_spending_users WHERE user_id = ?",
        (90,)
    )
    user = cursor.fetchone()
    conn.close()
    assert user is not None
    assert user['user_id'] == 90
    assert user['total_spending'] == 2500.0
    assert user['bonus_points'] == expected_bonus

def test_user_api(client):
    """Tests the /user/<user_id> endpoint."""
    response = client.get('/user/90')
    assert response.status_code == 200
    # Check that user details are present in the HTML response
    assert b'John Doe' in response.data
    assert b'john@example.com' in response.data
    assert b'25' in response.data  # Age

    # Optionally, check for total_spending
    assert b'250.0' in response.data  # Adjust based on your template's actual rendering
