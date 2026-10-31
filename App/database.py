import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "toserba_wartijaya_db"
}

def get_connection():
    temp_conn = mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )
    cursor = temp_conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
    cursor.close()
    temp_conn.close()

    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(150) NOT NULL,
            category VARCHAR(100) NOT NULL,
            price DECIMAL(12,2) NOT NULL,
            stock INT NOT NULL,
            is_fast_moving TINYINT DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INT AUTO_INCREMENT PRIMARY KEY,
            transaction_code VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            product_id INT NOT NULL,
            quantity INT NOT NULL,
            total_price DECIMAL(12,2) NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'Pemilik')")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('kasir', 'kasir123', 'Kasir')")
        conn.commit()
        
    cursor.close()
    conn.close()

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, role FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users

def add_user(username, password, role):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, password, role))
        conn.commit()
        success = True
    except Exception:
        success = False
    cursor.close()
    conn.close()
    return success

def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def update_product_price_stock(product_id, new_price, new_stock):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE products 
        SET price = %s, stock = stock + %s 
        WHERE id = %s
    """, (new_price, new_stock, product_id))
    conn.commit()
    cursor.close()
    conn.close()

def update_product_details(product_id, code, name, category, price):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products 
            SET code = %s, name = %s, category = %s, price = %s 
            WHERE id = %s
        """, (code, name, category, price, product_id))
        conn.commit()
        success = True
    except Exception:
        success = False
    cursor.close()
    conn.close()
    return success

def delete_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        success = True
    except Exception:
        success = False
    cursor.close()
    conn.close()
    return success