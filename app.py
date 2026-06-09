from flask import Flask,render_template, request, session, redirect, flash
import sqlite3

app = Flask(__name__)
app.secret_key = "hamo_store_secret"

@app.route('/', methods=['GET', 'POST'])
def login():

    error = None

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = cursor.fetchone()

        conn.close()

        if user:

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']

            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()

            today_sales = cursor.execute("""
                SELECT COUNT(*)
                FROM sales
                WHERE date(created_at)=date('now')
            """).fetchone()[0]

            today_amount = cursor.execute("""
                SELECT IFNULL(SUM(local_amount),0)
                FROM sales
                WHERE date(created_at)=date('now')
            """).fetchone()[0]

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
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    

    if request.method == 'POST':

        transaction_number = request.form['transaction_number']
        customer_name = request.form.get('customer_name', '')
        service = request.form['service']
        package = request.form['package']
        price = request.form['price']
        phone = request.form.get('phone', '')
        notes = request.form.get('notes', '')
        
        employee = session['username']
        currency_id = request.form['currency_id']
        currency = cursor.execute(
        "SELECT * FROM currencies WHERE id=?",
        (currency_id,)
        ).fetchone()

        exchange_rate = currency['rate']
        local_amount = float(price) * float(exchange_rate)
        exists = cursor.execute(
            "SELECT id FROM sales WHERE transaction_number=?",
            (transaction_number,)
        ).fetchone()

        if exists:

            flash("رقم العملية موجود مسبقاً")

        else:

            cursor.execute("""
                INSERT INTO sales
                (
                    transaction_number,
                    customer_name,
                    service,
                    package,
                    price,
                    currency_id,
                    exchange_rate,
                    local_amount,
                    phone,
                    notes,
                    employee,
                    created_at


                )
                VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                transaction_number,
                customer_name,
                service,
                package,
                price,
                currency_id,
                exchange_rate,
                local_amount,
                phone,
                notes,
                employee

            ))

            conn.commit()
            flash("تم حفظ العملية بنجاح")

    sales_data = cursor.execute(
        "SELECT * FROM sales ORDER BY id DESC LIMIT 10"
    ).fetchall()
    
    
    currencies = cursor.execute(
    "SELECT * FROM currencies ORDER BY name"
     ).fetchall()
    conn.close()
     
    return render_template(
        'sales.html',
        sales=sales_data,
        currencies=currencies
    )


@app.route('/currencies', methods=['GET', 'POST'])
def currencies():

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':

        code = request.form['code']
        name = request.form['name']
        rate = request.form['rate']

        cursor.execute("""
        INSERT INTO currencies (code, name, rate)
        VALUES (?, ?, ?)
        """, (code, name, rate))
        conn.commit()
    currencies = cursor.execute(
        "SELECT * FROM currencies ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template("currencies.html", currencies=currencies)

@app.route('/currencies/edit/<int:id>', methods=['GET', 'POST'])
def edit_currency(id):

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
	
    if request.method == 'POST':

     code = request.form['code']
     name = request.form['name']
     rate = request.form['rate']

     cursor.execute("""
    UPDATE currencies
    SET code=?,
        name=?,
        rate=?
    WHERE id=?
    """, (code, name, rate, id))

     conn.commit()
     conn.close()

     flash("تم تعديل العملة بنجاح")

     return redirect('/currencies')

    currency = cursor.execute(
    "SELECT * FROM currencies WHERE id=?",
    (id,)
    ).fetchone()

    conn.close()

    return render_template(
    'edit_currency.html',
    currency=currency
    )

@app.route('/currencies/delete/<int:id>')
def delete_currency(id):

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("DELETE FROM currencies WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/currencies')
@app.route('/currencies/base/<int:id>')
def set_base_currency(id):

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("UPDATE currencies SET is_base = 0")
    cursor.execute("UPDATE currencies SET is_base = 1 WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/currencies')

@app.route('/dashboard')
def dashboard():
     if 'user_id' not in session:
      return redirect('/')
     return render_template('dashboard.html')


@app.route('/reports')
def reports():
    if 'user_id' not in session:
     return redirect('/')
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

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
     query += " AND transaction_number LIKE ?"
     params.append(f"%{transaction_number}%")

    if from_date and to_date:
     query += " AND date(created_at) BETWEEN ? AND ?"
     params.extend([from_date, to_date])

    last_sales = cursor.execute(
    query + " ORDER BY id DESC LIMIT 100",
    params
).fetchall()

    today_sales = cursor.execute("""
     SELECT COUNT(*)
     FROM sales
     WHERE date(created_at)=date('now')
""").fetchone()[0]

    today_amount = cursor.execute("""
    SELECT IFNULL(SUM(local_amount),0)
    FROM sales
    WHERE date(created_at)=date('now')
""").fetchone()[0]
    
    
    
    month_amount = cursor.execute("""
    SELECT IFNULL(SUM(local_amount),0)
    FROM sales
    WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now')
""").fetchone()[0]

    expenses_total = cursor.execute("""
SELECT IFNULL(SUM(amount),0)
FROM expenses
""").fetchone()[0]

    net_profit = month_amount - expenses_total
    
    expenses = cursor.execute("""
SELECT *
FROM expenses
ORDER BY id DESC
""").fetchall()
    
    employees_report = cursor.execute("""
    SELECT
        employee,
        COUNT(*) as total_sales,
        IFNULL(SUM(local_amount),0) as total_amount
    FROM sales
    GROUP BY employee
    ORDER BY total_amount DESC
""").fetchall()
     
    service_report = cursor.execute("""
    SELECT
        service,
        COUNT(*) as total_sales,
        IFNULL(SUM(local_amount),0) as total_amount
    FROM sales
    GROUP BY service
    ORDER BY total_amount DESC
""").fetchall()

    conn.close()

    return render_template(
    "reports.html",
    last_sales=last_sales,
    today_sales=today_sales,
    today_amount=today_amount,
    month_amount=month_amount,
    expenses_total=expenses_total,
    net_profit=net_profit,
    expenses =expenses,
    employees_report=employees_report,
    service_report=service_report
)

@app.route('/employees', methods=['GET', 'POST'])
def employees():
    if 'user_id' not in session:
     return redirect('/')
    if session.get('role') != 'admin':
       flash('ليس لديك صلاحية')
       return redirect('/')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':

     full_name = request.form['full_name']
     username = request.form['username']
     password = request.form['password']
     role = request.form['role']
     status = request.form['status']

     cursor.execute("""
     INSERT INTO users
     (
        username,
        password,
        full_name,
        role,
        status,
        created_at
     )
     VALUES (?, ?, ?, ?, ?, datetime('now'))
    """,
     (
        username,
        password,
        full_name,
        role,
        status
     ))

     conn.commit()

     flash("تم إضافة الموظف بنجاح")

    users = cursor.execute("""
    SELECT *
    FROM users
    ORDER BY id DESC
""").fetchall()

    total_users = cursor.execute(
    "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    active_users = cursor.execute(
    "SELECT COUNT(*) FROM users WHERE status=1"
).fetchone()[0]

    admins = cursor.execute(
    "SELECT COUNT(*) FROM users WHERE role='admin'"
).fetchone()[0]

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

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':

     cursor.execute("""
    UPDATE users
    SET full_name=?,
        username=?,
        password=?,
        role=?,
        status=?
    WHERE id=?
    """,
    (
        request.form['full_name'],
        request.form['username'],
        request.form['password'],
        request.form['role'],
        request.form['status'],
        id
    ))

     conn.commit()
     conn.close()

     flash("تم تعديل الموظف بنجاح")

     return redirect('/employees')

    user = cursor.execute(
    "SELECT * FROM users WHERE id=?",
    (id,)
).fetchone()

    conn.close()

    return render_template(
    "edit_employee.html",
    user=user
)
    
@app.route('/expenses', methods=['GET', 'POST'])
def expenses():

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':

        cursor.execute("""
        INSERT INTO expenses (title, amount, notes, created_at)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (
            request.form['title'],
            request.form['amount'],
            request.form['notes']
        ))

        conn.commit()
        flash("تم إضافة المصروف بنجاح")

    expenses_list = cursor.execute("""
    SELECT *
    FROM expenses
    ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "expenses.html",
        expenses=expenses_list
    )
@app.route('/invoice/<int:id>')
def invoice(id):

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sale = cursor.execute("""
    SELECT *
    FROM sales
    WHERE id=?
    """, (id,)).fetchone()

    conn.close()

    return render_template(
        "invoice.html",
        sale=sale
    )

@app.route('/employees/delete/<int:id>')
def delete_employee(id):
 if 'user_id' not in session:
  return redirect('/')    
 conn = sqlite3.connect('database.db')
 cursor = conn.cursor()

 cursor.execute(
    "DELETE FROM users WHERE id=?",
    (id,)
)

 conn.commit()
 conn.close()

 flash("تم حذف الموظف")

 return redirect('/employees')

@app.route('/logout')
def logout():
 
 session.clear()

 return redirect('/')

 
if __name__ == '__main__': 
        app.run(debug=True)