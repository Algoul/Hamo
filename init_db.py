import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="hamo_store",
    user="postgres",
    password="YOUR_PASSWORD"
)

cursor = conn.cursor()

# ======================
# DROP TABLES
#cursor.execute("DROP TABLE IF EXISTS sales CASCADE")
# ======================
# ======================
# SALES TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    transaction_number TEXT UNIQUE,
    customer_name TEXT,
    service TEXT,
    package TEXT,
    price NUMERIC(18,2),
    visa_type TEXT,
    currency_id INTEGER,
    exchange_rate NUMERIC(18,6),
    local_amount NUMERIC(18,2),
    phone TEXT,
    notes TEXT,
    employee TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ======================
# CURRENCIES TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS currencies (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE,
    name TEXT,
    rate NUMERIC(18,6),
    is_base INTEGER DEFAULT 0
)
""")

# ======================
# USERS TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT,
    full_name TEXT,
    permissions TEXT,
    role TEXT DEFAULT 'sales',
    status INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_admin INTEGER DEFAULT 0
)
""")

# ======================
# ADMIN USER
# ======================

cursor.execute("""
INSERT INTO users
(
    username,
    password,
    full_name,
    permissions,
    role,
    status,
    is_admin
)
VALUES
(
    'admin',
    'admin123',
    'مدير النظام',
    'sales,reports,currencies,employees,expenses',
    'admin',
    1,
    1
)
ON CONFLICT (username) DO NOTHING
""")

# ======================
# EXPENSES TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    notes TEXT,
    employee TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ======================
# SERVICES TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS services (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
)
""")

cursor.execute("""
INSERT INTO services (name)
VALUES ('TikTok Coin')
ON CONFLICT (name) DO NOTHING
""")

cursor.execute("""
INSERT INTO services (name)
VALUES ('PUBG UC')
ON CONFLICT (name) DO NOTHING
""")

cursor.execute("""
INSERT INTO services (name)
VALUES ('Free Fire')
ON CONFLICT (name) DO NOTHING
""")

# ======================
# PURCHASES TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    currency_id INTEGER,
    quantity NUMERIC(18,2),
    purchase_rate NUMERIC(18,6),
    total_amount NUMERIC(18,2),
    supplier TEXT,
    notes TEXT,
    employee TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ======================
# CUSTOMERS TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT,
    phone TEXT,
    total_amount NUMERIC(18,2),
    paid_amount NUMERIC(18,2),
    notes TEXT,
    remaining_amount NUMERIC(18,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ======================
# ACCOUNTS TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    name TEXT,
    currency TEXT,
    balance NUMERIC(18,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ======================
# ACCOUNT TRANSACTIONS
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS account_transactions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER,
    type TEXT,
    amount NUMERIC(18,2),
    balance_after NUMERIC(18,2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ======================
# VISA GAFAR TABLE
# ======================

cursor.execute("""
CREATE TABLE IF NOT EXISTS visa_gafar (
    id SERIAL PRIMARY KEY,
    transaction_type TEXT,
    amount NUMERIC(18,2),
    package TEXT,
    sale_id INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("تم إنشاء قاعدة بيانات PostgreSQL بنجاح")
