import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# ======================
# SALES TABLE
# ======================
cursor.execute("DROP TABLE IF EXISTS sales")

cursor.execute('''
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_number TEXT UNIQUE,
    customer_name TEXT,
    service TEXT,
    package TEXT,
    price REAL,
    visa_type TEXT,
    currency_id INTEGER,
    exchange_rate REAL,
    local_amount REAL,
    phone TEXT,
    notes TEXT,
    employee TEXT,
    created_at TEXT
               )
''')

# ======================
# CURRENCIES TABLE
# ======================
cursor.execute('''
CREATE TABLE IF NOT EXISTS currencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT,
    rate REAL,
    is_base INTEGER DEFAULT 0
)
''')

# ======================
# USERS TABLE (FIXED)
# ======================
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    full_name TEXT,
    permissions TEXT,
    role TEXT DEFAULT 'sales',
    status INTEGER DEFAULT 1,
    created_at TEXT,
    is_admin INTEGER DEFAULT 0
)
''')

# ======================
# ADMIN USER (FIXED)
# ======================
cursor.execute("""
INSERT OR IGNORE INTO users
(
    username,
    password,
    full_name,
    permissions,
    role,
    status,
    created_at,
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
    datetime('now'),
    1
)
""")

# ======================
# EXPENSES TABLE
# ======================
cursor.execute('''
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    amount REAL NOT NULL,
    notes TEXT,
    employee TEXT,
    created_at TEXT
)
''')
# ======================
# servises TABLE
# ======================

cursor.execute('''
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
''')
cursor.execute("INSERT OR IGNORE INTO services (name) VALUES ('TikTok Coin')")
cursor.execute("INSERT OR IGNORE INTO services (name) VALUES ('PUBG UC')")
cursor.execute("INSERT OR IGNORE INTO services (name) VALUES ('Free Fire')")
# ======================
# purchases TABLE
# ======================

cursor.execute('''
CREATE TABLE IF NOT EXISTS purchases (

id INTEGER PRIMARY KEY AUTOINCREMENT,

currency_id INTEGER,

quantity REAL,

purchase_rate REAL,

total_amount REAL,

supplier TEXT,

notes TEXT,

employee TEXT,

created_at TEXT

)
''')

cursor.execute('''

CREATE TABLE IF NOT EXISTS accounts (

id INTEGER PRIMARY KEY AUTOINCREMENT,

name TEXT,

currency TEXT,

balance REAL DEFAULT 0,

created_at TEXT

)
''')
               
cursor.execute('''

CREATE TABLE IF NOT EXISTS account_transactions (

id INTEGER PRIMARY KEY AUTOINCREMENT,

account_id INTEGER,

type TEXT,

amount REAL,

balance_after REAL,

notes TEXT,

created_at TEXT

)
''')

conn.commit()
conn.close()
print("تم إنشاء قاعدة البيانات بنجاح")