import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()





cursor.execute("DROP TABLE IF EXISTS sales")

cursor.execute('''
CREATE TABLE sales (
id INTEGER PRIMARY KEY AUTOINCREMENT,
transaction_number TEXT UNIQUE,
customer_name TEXT,
service TEXT,
package TEXT,
price REAL,

currency_id INTEGER,
exchange_rate REAL,
local_amount REAL,

phone TEXT,
notes TEXT,
employee TEXT,
created_at TEXT

)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS currencies (
id INTEGER PRIMARY KEY AUTOINCREMENT,
code TEXT UNIQUE,
name TEXT,
rate REAL,
is_base INTEGER DEFAULT 0
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY AUTOINCREMENT,

username TEXT UNIQUE,
password TEXT,

full_name TEXT,

role TEXT DEFAULT 'sales',

status INTEGER DEFAULT 1,

created_at TEXT,

is_admin INTEGER DEFAULT 0

)
''')

cursor.execute("""
INSERT OR IGNORE INTO users
(
username,
password,
full_name,
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
'admin',
1,
datetime('now'),
1
)
""")
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


print("تم إنشاء قاعدة البيانات بنجاح")
conn.commit()
conn.close()