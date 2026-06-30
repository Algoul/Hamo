from flask import Flask, render_template, request, session, redirect, flash, send_file
import psycopg2
import os
import csv
import json
import zipfile
import tempfile
from datetime import datetime
from decimal import Decimal
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "hamo_store_secret"

@app.template_filter('money')
def money(value):
    try:
        return "{:,.0f}".format(float(value))
    except:
        return value

def get_db_connection():
    return psycopg2.connect(
            os.environ.get("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )

@app.route('/', methods=['GET', 'POST'])
def login():

    error = None

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, password)
        )

        user = cursor.fetchone()

        conn.close()

        if user:

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['permissions'] = user['permissions']

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*)
                FROM sales
                WHERE DATE(created_at)=CURRENT_DATE
            """)
            today_sales = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COALESCE(SUM(local_amount),0) AS total
                FROM sales
                WHERE DATE(created_at)=CURRENT_DATE
            """)
            today_amount = cursor.fetchone()['total']

            conn.close()

            return render_template(
                "dashboard.html",
                today_sales=today_sales,
                today_amount=today_amount
            )

        else:
            error = "اسم المستخدم أو كلمة المرور غير صحيحة"

    return render_template(
        "login.html",
        error=error
    )

@app.route('/sales', methods=['GET', 'POST'])
def sales():

    if 'user_id' not in session:
        return redirect('/')

    

    conn = get_db_connection()
    cursor = conn.cursor()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page

    if request.method == 'POST':

        transaction_number = request.form['transaction_number']
        customer_name = request.form.get('customer_name', '')
        service = request.form['service']
        package = request.form['package']
        price = request.form['price']
        visa_type = request.form['visa_type']
        phone = request.form.get('phone', '')
        notes = request.form.get('notes', '')

        employee = session['username']
        currency_id = request.form['currency_id']
        account_id = request.form['account_id']

        # جلب العملة
        cursor.execute(
            "SELECT * FROM currencies WHERE id=%s",
            (currency_id,)
        )
        currency = cursor.fetchone()

        exchange_rate = currency['rate']
        local_amount = float(price) * float(exchange_rate)

        # منع التكرار
        cursor.execute(
            "SELECT id FROM sales WHERE transaction_number=%s",
            (transaction_number,)
        )
        exists = cursor.fetchone()

        if exists:
            flash("رقم العملية موجود مسبقاً")
        
        else:

            # إدخال البيع
            cursor.execute("""
                INSERT INTO sales
                (
                    transaction_number,
                    customer_name,
                    service,
                    package,
                    price,
                    visa_type,
                    currency_id,
                    account_id,
                    exchange_rate,
                    local_amount,
                    phone,
                    notes,
                    employee,
                    created_at
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                RETURNING id
            """, (
                transaction_number,
                customer_name,
                service,
                package,
                price,
                visa_type,
                currency_id,
                account_id,
                exchange_rate,
                local_amount,
                phone,
                notes,
                employee
            ))

            sale_id = cursor.fetchone()['id']

            # تحديث الحساب
            cursor.execute("""
                UPDATE accounts
                SET balance = balance + %s
                WHERE id = %s
            """, (
                local_amount,
                account_id
            ))

            # تسجيل الحركة
            cursor.execute("""
                INSERT INTO account_transactions
                (
                    account_id,
                    type,
                    amount,
                    balance_after,
                    notes
                )
                VALUES (%s,%s,%s,
                    (SELECT balance FROM accounts WHERE id=%s),
                    %s)
            """, (
                account_id,
                'sale',
                local_amount,
                account_id,
                transaction_number
            ))

            # Visa Gafar
            if visa_type == "Visa Gafar":
                cursor.execute("""
                    INSERT INTO visa_gafar
                    (
                        transaction_type,
                        amount,
                        package,
                        sale_id,
                        created_at
                    )
                    VALUES
                    ('sale',%s,%s,%s,NOW())
                """, (
                    local_amount,
                    package,
                    sale_id
                ))

            conn.commit()
            flash("تم حفظ العملية بنجاح")

            return redirect('/sales')

    
    cursor.execute("""
    SELECT *
    FROM sales
    ORDER BY id DESC
    LIMIT %s OFFSET %s
""", (
    per_page,
    offset
))

    sales_data = cursor.fetchall()

    cursor.execute("""
    SELECT COUNT(*) AS total
    FROM sales
""")

    total = cursor.fetchone()['total']

    total_pages = (total + per_page - 1) // per_page

    cursor.execute("SELECT * FROM currencies ORDER BY name")
    currencies = cursor.fetchall()

    cursor.execute("SELECT * FROM services ORDER BY name")
    services = cursor.fetchall()

    cursor.execute("SELECT * FROM accounts ORDER BY name")
    accounts = cursor.fetchall()


    # 📅 مبيعات اليوم
    cursor.execute("""
    SELECT COUNT(*) FROM sales
    WHERE DATE(created_at)=CURRENT_DATE
""")
    today_sales = cursor.fetchone()['count']

    cursor.execute("""
    SELECT COALESCE(SUM(local_amount),0)
    FROM sales
    WHERE DATE(created_at)=CURRENT_DATE
""")
    today_amount = cursor.fetchone()['coalesce']

# 💸 مصروفات اليوم
    cursor.execute("""
    SELECT COALESCE(SUM(amount),0)
    FROM expenses
    WHERE DATE(created_at)=CURRENT_DATE
""")
    today_expenses = cursor.fetchone()['coalesce']

# 🛒 مشتريات اليوم
    cursor.execute("""
    SELECT COALESCE(SUM(total_amount),0)
    FROM purchases
    WHERE DATE(created_at)=CURRENT_DATE
""")
    today_purchases = cursor.fetchone()['coalesce']

# 💰 صافي ربح اليوم
    today_profit = float(today_amount or 0) - float(today_expenses or 0) - float(today_purchases or 0)

# 📄 آخر عمليات اليوم
    cursor.execute("""
    SELECT *
    FROM sales
    WHERE DATE(created_at)=CURRENT_DATE
    ORDER BY id DESC
    LIMIT 10
""")
    today_last_sales = cursor.fetchall()
    conn.close()

    return render_template(
        'sales.html',
        sales=sales_data,
        currencies=currencies,
        services=services,
        accounts=accounts,
        today_sales=today_sales,
        today_amount=today_amount,
        today_expenses=today_expenses,
        today_purchases=today_purchases,
        today_profit=today_profit,
        today_last_sales=today_last_sales,
        page=page,
        total_pages=total_pages

    )

@app.route('/sales/delete/<int:id>')
def delete_sale(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    # جلب العملية
    cursor.execute("""
        SELECT local_amount, account_id, visa_type, transaction_number
        FROM sales
        WHERE id=%s
    """, (id,))

    sale = cursor.fetchone()

    if sale:

        # خصم من الحساب
        cursor.execute("""
            UPDATE accounts
            SET balance = balance - %s
            WHERE id = %s
        """, (
            sale['local_amount'],
            sale['account_id']
        ))

        # حذف حركة الحساب باستخدام transaction_number
        cursor.execute("""
            DELETE FROM account_transactions
            WHERE notes = %s
        """, (
            sale['transaction_number'],
        ))

        # حذف Visa Gafar إذا موجود
        if sale['visa_type'] == "Visa Gafar":
            cursor.execute("""
                DELETE FROM visa_gafar
                WHERE sale_id = %s
            """, (id,))

        # حذف البيع
        cursor.execute("""
            DELETE FROM sales
            WHERE id = %s
        """, (id,))

        conn.commit()

    conn.close()

    return redirect('/sales')
@app.route('/debug/sales')
def debug_sales():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM sales
    """)
    count = cursor.fetchone()['total']

    cursor.execute("""
        SELECT MIN(created_at) AS first_date,
               MAX(created_at) AS last_date
        FROM sales
    """)
    dates = cursor.fetchone()

    conn.close()

    return {
        "total_sales": count,
        "first_date": str(dates['first_date']),
        "last_date": str(dates['last_date'])
    }

@app.route('/services', methods=['GET', 'POST'])
def services():

 if 'user_id' not in session:
    return redirect('/')

 conn = get_db_connection()
 cursor = conn.cursor()

 if request.method == 'POST':

    name = request.form['name']

    cursor.execute(
        "INSERT INTO services (name) VALUES (%s)",
        (name,)
    )

    conn.commit()

 cursor.execute(
    "SELECT * FROM services ORDER BY name"
)
 services = cursor.fetchall()

 conn.close()

 return render_template(
    "services.html",
    services=services
)

@app.route('/services/delete/<int:id>')
def delete_service(id):

 conn = get_db_connection()
 cursor = conn.cursor()

 cursor.execute(
    "DELETE FROM services WHERE id=%s",
    (id,)
)

 conn.commit()
 conn.close()

 return redirect('/services')

@app.route('/purchases', methods=['GET', 'POST'])
def purchases():

 if 'user_id' not in session:
    return redirect('/')

 conn = get_db_connection()
 cursor = conn.cursor()

 if request.method == 'POST':

    currency_id = request.form['currency_id']
    quantity = float(request.form['quantity'])
    purchase_rate = float(request.form['purchase_rate'])

    total_amount = quantity * purchase_rate

    supplier = request.form['supplier']
    notes = request.form['notes']

    cursor.execute("""
    INSERT INTO purchases
    (
        currency_id,
        quantity,
        purchase_rate,
        total_amount,
        supplier,
        notes,
        employee,
        created_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """,
    (
        currency_id,
        quantity,
        purchase_rate,
        total_amount,
        supplier,
        notes,
        session['username']
    ))

    conn.commit()
    flash("تم حفظ عملية الشراء بنجاح")

 cursor.execute("""
SELECT purchases.*,
       currencies.name AS currency_name
FROM purchases
LEFT JOIN currencies
ON purchases.currency_id = currencies.id
ORDER BY purchases.id DESC
""")
 purchases_list = cursor.fetchall()

 cursor.execute("""
SELECT *
FROM currencies
ORDER BY name
""")
 currencies = cursor.fetchall()

 conn.close()

 return render_template(
    "purchases.html",
    purchases=purchases_list,
    currencies=currencies
)

@app.route('/purchases/delete/<int:id>')
def delete_purchase(id):

 if session.get('role') != 'admin':
    return "غير مصرح", 403

 conn = get_db_connection()
 cursor = conn.cursor()

 cursor.execute(
    "DELETE FROM purchases WHERE id=%s",
    (id,)
)

 conn.commit()
 conn.close()

 return redirect('/purchases')

@app.route('/currencies', methods=['GET', 'POST'])
def currencies():

 conn = get_db_connection()
 cursor = conn.cursor()

 if request.method == 'POST':

    code = request.form['code']
    name = request.form['name']
    rate = request.form['rate']

    cursor.execute("""
    INSERT INTO currencies (code, name, rate)
    VALUES (%s, %s, %s)
    """, (code, name, rate))

    conn.commit()

 cursor.execute(
    "SELECT * FROM currencies ORDER BY name"
)
 currencies = cursor.fetchall()

 conn.close()

 return render_template(
    "currencies.html",
    currencies=currencies
)

@app.route('/currencies/edit/<int:id>', methods=['GET', 'POST'])
def edit_currency(id):

 conn = get_db_connection()
 cursor = conn.cursor()

 if request.method == 'POST':

    code = request.form['code']
    name = request.form['name']
    rate = request.form['rate']

    cursor.execute("""
    UPDATE currencies
    SET code=%s,
        name=%s,
        rate=%s
    WHERE id=%s
    """,
    (
        code,
        name,
        rate,
        id
    ))

    conn.commit()
    conn.close()

    flash("تم تعديل العملة بنجاح")

    return redirect('/currencies')

 cursor.execute(
    "SELECT * FROM currencies WHERE id=%s",
    (id,)
)
 currency = cursor.fetchone()

 conn.close()

 return render_template(
    'edit_currency.html',
    currency=currency
)

@app.route('/currencies/delete/<int:id>')
def delete_currency(id):

 conn = get_db_connection()
 cursor = conn.cursor()

 cursor.execute(
    "DELETE FROM currencies WHERE id=%s",
    (id,)
)

 conn.commit()
 conn.close()

 return redirect('/currencies')

@app.route('/currencies/base/<int:id>')
def set_base_currency(id):

 conn = get_db_connection()
 cursor = conn.cursor()

 cursor.execute(
    "UPDATE currencies SET is_base = 0"
)

 cursor.execute(
    "UPDATE currencies SET is_base = 1 WHERE id=%s",
    (id,)
)

 conn.commit()
 conn.close()

 return redirect('/currencies')
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM sales
        WHERE DATE(created_at)=CURRENT_DATE
    """)
    today_sales = cursor.fetchone()['count']

    cursor.execute("""
        SELECT COALESCE(SUM(local_amount),0) AS total
        FROM sales
        WHERE DATE(created_at)=CURRENT_DATE
    """)
    today_amount = cursor.fetchone()['total']

    conn.close()

    return render_template(
        'dashboard.html',
        today_sales=today_sales,
        today_amount=today_amount
    )

@app.route('/reports')
def reports():

 if 'user_id' not in session:
    return redirect('/')

 conn = get_db_connection()
 cursor = conn.cursor()
 page = request.args.get('page', 1, type=int)
 per_page = 50
 offset = (page - 1) * per_page

 from_date = request.args.get('from_date')
 to_date = request.args.get('to_date')
 transaction_number = request.args.get('transaction_number')
 query = """
SELECT *
FROM sales
WHERE 1=1
"""

 params = []

 if transaction_number:
    query += " AND transaction_number ILIKE %s"
    params.append(f"%{transaction_number}%")

 if from_date and to_date:
    query += " AND DATE(created_at) BETWEEN %s AND %s"
    params.extend([from_date, to_date])
    
 cursor.execute(
    query + " ORDER BY id DESC LIMIT %s OFFSET %s",
    params + [per_page, offset]
)
 last_sales = cursor.fetchall()

 cursor.execute(
    "SELECT COUNT(*) FROM sales"
)
 total = cursor.fetchone()['count']

 total_pages = (total + per_page - 1) // per_page

 cursor.execute("""
    SELECT COUNT(*)
    FROM sales
    WHERE DATE(created_at)=CURRENT_DATE
""")
 today_sales = cursor.fetchone()['count']

 cursor.execute("""
    SELECT COALESCE(SUM(local_amount),0) AS total
    FROM sales
    WHERE DATE(created_at)=CURRENT_DATE
""")
 today_amount = cursor.fetchone()['total']

 cursor.execute("""
    SELECT COALESCE(SUM(local_amount),0) AS total
    FROM sales
    WHERE TO_CHAR(created_at,'YYYY-MM')
    = TO_CHAR(CURRENT_DATE,'YYYY-MM')
""")
 month_amount = cursor.fetchone()['total']

 cursor.execute("""
    SELECT COALESCE(SUM(amount),0) AS total
    FROM expenses
""")
 expenses_total = cursor.fetchone()['total']

 cursor.execute("""
    SELECT COALESCE(SUM(total_amount),0) AS total
    FROM purchases
""")
 purchases_total = cursor.fetchone()['total']

 net_profit = month_amount - purchases_total - expenses_total

 cursor.execute("""
    SELECT *
    FROM expenses
    ORDER BY id DESC
""")
 expenses = cursor.fetchall()

 cursor.execute("""
    SELECT
        employee,
        COUNT(*) AS total_sales,
        COALESCE(SUM(local_amount),0) AS total_amount
    FROM sales
    GROUP BY employee
    ORDER BY total_amount DESC
""")
 employees_report = cursor.fetchall()

 cursor.execute("""
    SELECT
        service,
        COUNT(*) AS total_sales,
        COALESCE(SUM(local_amount),0) AS total_amount
    FROM sales
    GROUP BY service
    ORDER BY total_amount DESC
""")
 service_report = cursor.fetchall()

 conn.close()

 return render_template(
    "reports.html",
    last_sales=last_sales,
    page=page,
    total_pages=total_pages,
    today_sales=today_sales,
    today_amount=today_amount,
    month_amount=month_amount,
    expenses_total=expenses_total,
    purchases_total=purchases_total,
    net_profit=net_profit,
    expenses=expenses,
    employees_report=employees_report,
    service_report=service_report
)

@app.route('/customers', methods=['GET', 'POST'])
def customers():

 if 'user_id' not in session:
    return redirect('/')

 conn = get_db_connection()
 cursor = conn.cursor()

 if request.method == 'POST':

    name = request.form['name']
    phone = request.form['phone']
    total_amount = request.form['total_amount']
    notes = request.form['notes']

    cursor.execute("""
    INSERT INTO customers
    (
        name,
        phone,
        total_amount,
        paid_amount,
        remaining_amount,
        notes,
        created_at
    )
    VALUES (%s, %s, %s, 0, %s, %s, NOW())
    """,
    (
        name,
        phone,
        total_amount,
        total_amount,
        notes
    ))

    conn.commit()

    flash("تم إضافة العميل بنجاح")

 cursor.execute("""
    SELECT *
    FROM customers
    ORDER BY id DESC
""")
 customers = cursor.fetchall()

 conn.close()

 return render_template(
    'customers.html',
    customers=customers
)

@app.route('/customers/delete/<int:id>')
def delete_customer(id):

 if 'user_id' not in session:
    return redirect('/')

 conn = get_db_connection()
 cursor = conn.cursor()

 cursor.execute(
    "DELETE FROM customers WHERE id=%s",
    (id,)
)

 conn.commit()
 conn.close()

 flash("تم حذف العميل بنجاح")

 return redirect('/customers')

@app.route('/customers/payment/<int:id>', methods=['GET', 'POST'])
def customer_payment(id):

 if 'user_id' not in session:
    return redirect('/')

 conn = get_db_connection()
 cursor = conn.cursor()

 cursor.execute(
    "SELECT * FROM customers WHERE id=%s",
    (id,)
 )
 customer = cursor.fetchone()

 if request.method == 'POST':

    payment = Decimal(request.form['payment'])

    new_paid = customer['paid_amount'] + payment

    new_remaining = (
        customer['total_amount'] - new_paid
    )

    cursor.execute("""
    UPDATE customers
    SET paid_amount=%s,
        remaining_amount=%s
    WHERE id=%s
    """,
    (
        new_paid,
        new_remaining,
        id
    ))

    conn.commit()
    conn.close()

    flash("تم تسجيل الدفعة")

    return redirect('/customers')

 conn.close()

 return render_template(
    "customer_payment.html",
    customer=customer
)
@app.route('/employees', methods=['GET', 'POST'])
def employees():

    if 'user_id' not in session:
        return redirect('/')

    if session.get('role') != 'admin':
        flash('ليس لديك صلاحية')
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        full_name = request.form['full_name']
        username = request.form['username']
        password = request.form['password']
        permissions = ",".join(request.form.getlist("permissions"))
        status = request.form['status']

        cursor.execute("""
        INSERT INTO users
        (
            username,
            password,
            full_name,
            role,
            permissions,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            username,
            password,
            full_name,
            'sale',
            permissions,
            status
        ))

        conn.commit()

        flash("تم إضافة الموظف بنجاح")

    cursor.execute("""
    SELECT *
    FROM users
    ORDER BY id DESC
    """)
    users = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM users WHERE status=1")
    active_users = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role='admin'")
    admins = cursor.fetchone()['total']

    conn.close()

    return render_template(
        'employees.html',
        users=users,
        total_users=total_users,
        active_users=active_users,
        admins=admins
    )


@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        permissions = ",".join(
            request.form.getlist("permissions")
        )

        cursor.execute("""
        UPDATE users
        SET full_name=%s,
            username=%s,
            password=%s,
            permissions=%s,
            role=%s,
            status=%s
        WHERE id=%s
        """,
        (
            request.form['full_name'],
            request.form['username'],
            request.form['password'],
            permissions,
            request.form['role'],
            request.form['status'],
            id
        ))

        conn.commit()
        conn.close()

        flash("تم تعديل الموظف بنجاح")

        return redirect('/employees')

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (id,)
    )

    user = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_employee.html",
        user=user
    )


@app.route('/expenses', methods=['GET', 'POST'])
def expenses():

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        cursor.execute("""
        INSERT INTO expenses
        (
            title,
            amount,
            notes,
            created_at
        )
        VALUES
        (
            %s,
            %s,
            %s,
            NOW()
        )
        """,
        (
            request.form['title'],
            request.form['amount'],
            request.form['notes']
        ))

        conn.commit()

        flash("تم إضافة المصروف بنجاح")

    cursor.execute("""
    SELECT *
    FROM expenses
    ORDER BY id DESC
    """)

    expenses_list = cursor.fetchall()

    conn.close()

    return render_template(
        "expenses.html",
        expenses=expenses_list
    )


@app.route('/invoice/<int:id>')
def invoice(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM sales
    WHERE id=%s
    """, (id,))

    sale = cursor.fetchone()

    conn.close()

    return render_template(
        "invoice.html",
        sale=sale
    )


@app.route('/employees/delete/<int:id>')
def delete_employee(id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM users WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    flash("تم حذف الموظف")

    return redirect('/employees')


@app.route('/accounts', methods=['GET', 'POST'])
def accounts():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        name = request.form['name']
        currency = request.form['currency']
        balance = request.form['balance']

        cursor.execute("""
        INSERT INTO accounts
        (
            name,
            currency,
            balance,
            created_at
        )
        VALUES
        (
            %s,
            %s,
            %s,
            NOW()
        )
        RETURNING id
        """,
        (
            name,
            currency,
            balance
        ))

        account_id = cursor.fetchone()['id']

        cursor.execute("""
        INSERT INTO account_transactions
        (
            account_id,
            type,
            amount,
            balance_after,
            notes,
            created_at
        )
        VALUES
        (
            %s,
            'رصيد افتتاحي',
            %s,
            %s,
            '',
            NOW()
        )
        """,
        (
            account_id,
            balance,
            balance
        ))

        conn.commit()

        flash("تم إنشاء الحساب بنجاح")

    cursor.execute("""
    SELECT *
    FROM accounts
    ORDER BY id DESC
    """)

    accounts = cursor.fetchall()

    conn.close()

    return render_template(
        'accounts.html',
        accounts=accounts
    )


@app.route('/accounts/deposit/<int:id>', methods=['POST'])
def deposit(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    amount = Decimal(request.form['amount'])

    cursor.execute(
        "SELECT balance FROM accounts WHERE id=%s",
        (id,)
    )

    account = cursor.fetchone()
    old_balance = account['balance']

    new_balance = old_balance + amount

    cursor.execute("""
    UPDATE accounts
    SET balance=%s
    WHERE id=%s
    """,
    (
        new_balance,
        id
    ))

    cursor.execute("""
    INSERT INTO account_transactions
    (
        account_id,
        type,
        amount,
        balance_after,
        created_at
    )
    VALUES
    (
        %s,
        'deposit',
        %s,
        %s,
        NOW()
    )
    """,
    (
        id,
        amount,
        new_balance
    ))

    conn.commit()
    conn.close()

    return redirect('/accounts')


@app.route('/accounts/withdraw/<int:id>', methods=['POST'])
def withdraw(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    amount = Decimal(request.form['amount'])

    cursor.execute(
        "SELECT balance FROM accounts WHERE id=%s",
        (id,)
    )

    account = cursor.fetchone()
    old_balance = account['balance']

    new_balance = old_balance - amount

    cursor.execute("""
    UPDATE accounts
    SET balance=%s
    WHERE id=%s
    """,
    (
        new_balance,
        id
    ))

    cursor.execute("""
    INSERT INTO account_transactions
    (
        account_id,
        type,
        amount,
        balance_after,
        created_at
    )
    VALUES
    (
        %s,
        'withdraw',
        %s,
        %s,
        NOW()
    )
    """,
    (
        id,
        amount,
        new_balance
    ))

    conn.commit()
    conn.close()

    return redirect('/accounts')


@app.route('/accounts/delete/<int:id>')
def delete_account(id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM accounts WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    flash("تم حذف الحساب بنجاح")

    return redirect('/accounts')

@app.route('/reports/print')
def print_reports():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 📄 جلب كل المبيعات بدون LIMIT
    cursor.execute("""
        SELECT *
        FROM sales
        ORDER BY id ASC
    """)
    sales = cursor.fetchall()

    # 📊 إجمالي المبيعات
    cursor.execute("""
        SELECT COALESCE(SUM(local_amount),0)
        FROM sales
    """)
    total_sales = cursor.fetchone()['coalesce']

    # 💸 المصروفات
    cursor.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM expenses
    """)
    expenses = cursor.fetchone()['coalesce']

    # 🛒 المشتريات
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount),0)
        FROM purchases
    """)
    purchases = cursor.fetchone()['coalesce']

    # 💰 صافي الربح
    net_profit = float(total_sales or 0) - float(expenses or 0) - float(purchases or 0)

    conn.close()

    return render_template(
        "print_reports.html",
        sales=sales,
        total_sales=total_sales,
        expenses=expenses,
        purchases=purchases,
        net_profit=net_profit
    )
@app.route('/accounts/report/<int:id>')
def account_report(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM accounts WHERE id=%s",
        (id,)
    )
    account = cursor.fetchone()

    cursor.execute("""
    SELECT *
    FROM account_transactions
    WHERE account_id=%s
    ORDER BY id DESC
    """,
    (id,)
    )
    transactions = cursor.fetchall()

    conn.close()

    return render_template(
        'account_report.html',
        account=account,
        transactions=transactions
    )

import re

def package_to_number(value):
    if value is None:
        return 0

    value = str(value).strip().lower()

    if value.endswith("k"):
        try:
            return float(value[:-1]) * 1000
        except:
            return 0

    try:
        return float(value)
    except:
        return 0



@app.route('/visa_gafar')
def visa_gafar():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()



    # 🔥 جلب آخر دورة
    cursor.execute("""
        SELECT COALESCE(MAX(cycle),1) AS cycle
        FROM visa_gafar
    """)
    current_cycle = cursor.fetchone()['cycle']

    # 🔥 المبيعات حسب الدورة
    cursor.execute("""
        SELECT *
        FROM sales
        WHERE visa_type = 'Visa Gafar'
        ORDER BY id DESC
    """, (current_cycle,))

    sales = cursor.fetchall()

    # 🔥 تصنيف الجملة والقطاعي
    wholesale_sales = []
    retail_sales = []

    wholesale_amount = 0
    retail_amount = 0

    wholesale_packages = 0
    retail_packages = 0

    for sale in sales:

        qty = package_to_number(sale["package"])

        if qty >= 5000:

            wholesale_sales.append(sale)
            wholesale_amount += sale["local_amount"]
            wholesale_packages += qty

        else:

            retail_sales.append(sale)
            retail_amount += sale["local_amount"]
            retail_packages += qty

    # 🔥 إجمالي المبيعات (الدورة الحالية فقط)
    cursor.execute("""
        SELECT COALESCE(SUM(local_amount),0) AS total
        FROM sales
        WHERE visa_type='Visa Gafar'
        AND visa_cycle = %s
    """, (current_cycle,))

    total_amount = cursor.fetchone()['total']

    # 🔥 إجمالي الباقات
    cursor.execute("""
        SELECT COALESCE(
            SUM(
                CASE
                    WHEN package ~ '^[0-9]+k$'
                    THEN REPLACE(LOWER(package),'k','')::NUMERIC * 1000
                    WHEN package ~ '^[0-9]+$'
                    THEN package::NUMERIC
                    ELSE 0
                END
            ),0) AS total
        FROM sales
        WHERE visa_type='Visa Gafar'
        AND visa_cycle = %s
    """, (current_cycle,))

    total_packages = cursor.fetchone()['total']

    # 🔥 الإيداع والسحب (الدورة الحالية)
    cursor.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM visa_gafar
        WHERE transaction_type='deposit'
        AND cycle = %s
    """, (current_cycle,))

    total_deposit = cursor.fetchone()['total']

    cursor.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM visa_gafar
        WHERE transaction_type='withdraw'
        AND cycle = %s
    """, (current_cycle,))

    total_withdraw = cursor.fetchone()['total']

    balance = total_deposit - total_withdraw - total_amount

    conn.close()

    return render_template(
        "visa_gafar.html",
        sales=sales,
        wholesale_sales=wholesale_sales,
        retail_sales=retail_sales,
        wholesale_amount=wholesale_amount,
        retail_amount=retail_amount,
        wholesale_packages=wholesale_packages,
        retail_packages=retail_packages,
        total_amount=total_amount,
        total_packages=total_packages,
        balance=balance,
        current_cycle=current_cycle
    )



@app.route('/visa_gafar/deposit', methods=['POST'])
def visa_gafar_deposit():

    conn = get_db_connection()
    cursor = conn.cursor()

    amount = float(request.form['amount'])

    # 🔥 جلب الدورة الحالية
    cursor.execute("""
        SELECT COALESCE(MAX(cycle),1) AS cycle
        FROM visa_gafar
    """)
    current_cycle = cursor.fetchone()['cycle']

    # إدخال الإيداع
    cursor.execute("""
        INSERT INTO visa_gafar
        (transaction_type, amount, cycle, created_at)
        VALUES (%s,%s,%s,NOW())
    """, ('deposit', amount, current_cycle))

    conn.commit()
    conn.close()

    return redirect('/visa_gafar')


@app.route('/visa_gafar/withdraw', methods=['POST'])
def visa_gafar_withdraw():

    conn = get_db_connection()
    cursor = conn.cursor()

    amount = float(request.form['amount'])

    cursor.execute("""
        SELECT COALESCE(MAX(cycle),1) AS cycle
        FROM visa_gafar
    """)
    current_cycle = cursor.fetchone()['cycle']

    cursor.execute("""
        INSERT INTO visa_gafar
        (transaction_type, amount, cycle, created_at)
        VALUES (%s,%s,%s,NOW())
    """, ('withdraw', amount, current_cycle))

    conn.commit()
    conn.close()

    return redirect('/visa_gafar')



@app.route('/visa_gafar/delete/<int:id>')
def delete_visa_sale(id):

    if session.get('role') != 'admin':
        return "غير مصرح", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM sales
    WHERE id=%s
    AND visa_type='Visa Gafar'
    """,
    (id,)
    )

    conn.commit()
    conn.close()

    return redirect('/visa_gafar')
@app.route('/visa_gafar/cycles')
def visa_cycles():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔥 جلب كل الدورات الموجودة
    cursor.execute("""
        SELECT DISTINCT cycle
        FROM visa_gafar
        ORDER BY cycle DESC
    """)

    cycles = cursor.fetchall()

    all_cycles_data = []

    for c in cycles:

        cycle = c['cycle']

        # 🔥 إجمالي المبيعات
        cursor.execute("""
            SELECT COALESCE(SUM(amount),0) AS total
            FROM visa_gafar
            WHERE cycle=%s AND transaction_type='sale'
        """, (cycle,))

        sales_total = cursor.fetchone()['total']

        # 🔥 الإيداع
        cursor.execute("""
            SELECT COALESCE(SUM(amount),0) AS total
            FROM visa_gafar
            WHERE cycle=%s AND transaction_type='deposit'
        """, (cycle,))

        deposit = cursor.fetchone()['total']

        # 🔥 السحب
        cursor.execute("""
            SELECT COALESCE(SUM(amount),0) AS total
            FROM visa_gafar
            WHERE cycle=%s AND transaction_type='withdraw'
        """, (cycle,))

        withdraw = cursor.fetchone()['total']

        balance = deposit - withdraw - sales_total

        all_cycles_data.append({
            "cycle": cycle,
            "sales": sales_total,
            "deposit": deposit,
            "withdraw": withdraw,
            "balance": balance
        })

    conn.close()

    return render_template("visa_cycles.html", cycles=all_cycles_data)
@app.route('/backup/create')
def create_backup():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔥 جلب كل الجداول تلقائياً
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname='public'
    """)

    tables = [row['tablename'] for row in cursor.fetchall()]

    # 📁 مجلد مؤقت
    temp_dir = tempfile.mkdtemp()

    # 📦 تصدير كل جدول CSV
    for table in tables:

        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()

            file_path = os.path.join(temp_dir, f"{table}.csv")

            with open(file_path, "w", newline="", encoding="utf-8") as f:

                writer = csv.writer(f)

                if rows:
                    writer.writerow(rows[0].keys())

                    for row in rows:
                        writer.writerow(row.values())

        except Exception as e:
            print(f"Skip table {table}: {e}")

    # 📄 معلومات النسخة
    backup_info = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tables_count": len(tables),
        "system": "Flask Sales System"
    }

    info_path = os.path.join(temp_dir, "backup_info.json")

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(backup_info, f, ensure_ascii=False, indent=4)

    # 📦 إنشاء ملف ZIP
    zip_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = os.path.join(temp_dir, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:

        for file in os.listdir(temp_dir):

            if file.endswith(".csv") or file.endswith(".json"):

                zipf.write(
                    os.path.join(temp_dir, file),
                    arcname=file
                )

    conn.close()

    # 📥 تنزيل النسخة مباشرة
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=zip_name
    )
@app.route('/backup/restore', methods=['POST'])
def restore_backup():

    if 'user_id' not in session:
        return redirect('/')

    file = request.files['file']

    if not file:
        flash("لم يتم اختيار ملف")
        return redirect('/settings')

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "backup.zip")

    file.save(zip_path)

    extract_dir = os.path.join(temp_dir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    # فك الضغط
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    conn = get_db_connection()
    cursor = conn.cursor()

    # قراءة كل CSV وإرجاع البيانات
    for file_name in os.listdir(extract_dir):

        if file_name.endswith(".csv"):

            table_name = file_name.replace(".csv", "")
            file_path = os.path.join(extract_dir, file_name)

            with open(file_path, "r", encoding="utf-8") as f:

                reader = csv.DictReader(f)

                # 🧨 حذف البيانات القديمة
                cursor.execute(f"DELETE FROM {table_name}")

                for row in reader:

                    columns = list(row.keys())
                    values = list(row.values())

                    placeholders = ",".join(["%s"] * len(values))
                    cols = ",".join(columns)

                    cursor.execute(
                        f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})",
                        values
                    )

    conn.commit()
    conn.close()

    flash("تم استعادة النسخة الاحتياطية بنجاح")

    return redirect('/settings')

@app.route('/settings')
def settings():

    if 'user_id' not in session:
        return redirect('/')

    return render_template("settings.html")

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
