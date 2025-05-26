from collections import defaultdict
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import hashlib
from datetime import datetime, date, timedelta
import calendar

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management and flashing messages

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'employee_information'

SALT = 'qwertyuio123456'  # Salt for password hashing

mysql = MySQL(app)

BASE_SALARY = 30000
DEDUCTION_PER_ABSENT = BASE_SALARY / 22  # Assume 22 working days
DEDUCTION_PER_LATE = 150
DEDUCTION_PER_EARLY = 150

def get_month_days(year, month):
    days = []
    num_days = calendar.monthrange(year, month)[1]
    for d in range(1, num_days + 1):
        day_date = date(year, month, d)
        days.append({
            'date': day_date,
            'weekday': day_date.weekday()  # Monday=0 ... Sunday=6
        })
    return days

# ------------------ ROUTES ------------------

# Login Page
@app.route('/')
def login():
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Dashboard
@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM employee_info")
    employees = cur.fetchall()

    today = datetime.today().date()
    standard_in = datetime.strptime("08:10", "%H:%M").time()

    # Employees present today
    cur.execute("SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE DATE(attendance_date) = %s", (today,))
    present_today = cur.fetchone()[0]

    # Late employees today
    cur.execute("SELECT COUNT(*) FROM attendance WHERE DATE(attendance_date) = %s AND check_in_time > %s", (today, standard_in))
    late_today = cur.fetchone()[0]

    total_employees = len(employees)
    absent_today = total_employees - present_today

    # Weekly summary
    summary = defaultdict(lambda: {'present': 0, 'late': 0, 'absent': total_employees})
    for i in range(6, -1, -1):
        date_iter = today - timedelta(days=i)
        cur.execute("SELECT check_in_time FROM attendance WHERE DATE(attendance_date) = %s", (date_iter,))
        results = cur.fetchall()

        for row in results:
            check_in = row[0]
            summary[date_iter]['present'] += 1
            summary[date_iter]['absent'] -= 1
            if check_in and check_in > standard_in:
                summary[date_iter]['late'] += 1

    cur.close()

    labels = [d.strftime('%a') for d in summary.keys()]
    present_data = [v['present'] for v in summary.values()]
    late_data = [v['late'] for v in summary.values()]
    absent_data = [v['absent'] for v in summary.values()]

    return render_template(
        'home.html',
        employees=employees,
        username=session['username'],
        total_employees=total_employees,
        present_today=present_today,
        late_today=late_today,
        absent_today=absent_today,
        today=today.strftime('%B %d, %Y'),
        chart_labels=labels,
        present_data=present_data,
        late_data=late_data,
        absent_data=absent_data
    )

# Login/Register API
@app.route('/check-user', methods=['POST'])
def check_user():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required.'})

        hashed_password = hashlib.sha512((SALT + password).encode('utf-8')).hexdigest()
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user:
            if user[2] == hashed_password:
                session['username'] = username
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'message': 'Incorrect password'})
        else:
            # Register new user
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            mysql.connection.commit()
            session['username'] = username
            return jsonify({'success': True, 'message': 'User registered'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Employee List Page
@app.route('/employee-list')
def employee_list():
    if 'username' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM employee_info")
    employees = cur.fetchall()
    cur.close()

    return render_template('employee_list.html', employees=employees, username=session['username'])

# Add Employee
@app.route('/add-employee', methods=['POST'])
def add_employee():
    try:
        data = request.get_json()
        lastname = data.get('lastname')
        firstname = data.get('firstname')
        middlename = data.get('middlename')
        position = data.get('position')
        office = data.get('office')

        if not all([lastname, firstname, middlename, position, office]):
            return jsonify({'error': 'All fields are required.'}), 400

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO employee_info (lname, fname, mname, position, office)
            VALUES (%s, %s, %s, %s, %s)
        """, (lastname, firstname, middlename, position, office))
        mysql.connection.commit()
        cur.close()

        return jsonify({'success': True, 'message': 'Employee added successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Edit Employee
@app.route('/edit-employee', methods=['POST'])
def edit_employee():
    try:
        data = request.get_json()
        emp_id = data.get('id')
        lastname = data.get('lastname')
        firstname = data.get('firstname')
        middlename = data.get('middlename')
        position = data.get('position')
        office = data.get('office')

        if not all([emp_id, lastname, firstname, middlename, position, office]):
            return jsonify({'error': 'All fields are required.'}), 400

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE employee_info
            SET lname=%s, fname=%s, mname=%s, position=%s, office=%s
            WHERE employee_id=%s
        """, (lastname, firstname, middlename, position, office, emp_id))
        mysql.connection.commit()
        cur.close()

        return jsonify({'success': True, 'message': 'Employee updated successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Delete Employee
@app.route('/delete-employee', methods=['POST'])
def delete_employee():
    data = request.get_json()
    emp_id = data.get('id')

    if emp_id:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM employee_info WHERE employee_id = %s", (emp_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'failed'}), 400

# Get Employees (JSON)
@app.route('/get-employees', methods=['GET'])
def get_employees():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM employee_info")
        employees = cur.fetchall()
        cur.close()
        return jsonify(employees)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Attendance Record Page
@app.route('/attendance_record')
def attendance_record():
    # Get month/year from query or default to current month
    year = request.args.get('year', default=datetime.now().year, type=int)
    month = request.args.get('month', default=datetime.now().month, type=int)

    conn = mysql.connection
    cursor = conn.cursor()

    # Get all employees
    cursor.execute("SELECT employee_id, fname, lname, position, office FROM employee_info ORDER BY lname, fname")
    employees = cursor.fetchall()

    # Get all attendance for the month (both check_in and check_out) for all employees
    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    cursor.execute("""
        SELECT employee_id, attendance_date, check_in_time, check_out_time, status
        FROM attendance
        WHERE attendance_date BETWEEN %s AND %s
    """, (start_date, end_date))
    attendance_rows = cursor.fetchall()

    # Transform attendance rows into nested dict:
    # attendance_data[employee_id][date_str]['in' or 'out'] = status ('present', 'late', 'absent')
    attendance_data = {}
    attendance_counts = defaultdict(lambda: {'present': 0, 'late': 0, 'early': 0, 'absent': 0})

    for emp in employees:
        attendance_data[emp[0]] = {}

    for row in attendance_rows:
        emp_id = row[0]
        att_date = row[1].strftime('%Y-%m-%d')
        check_in = row[2]
        check_out = row[3]
        status = row[4] or 'present'

        if emp_id not in attendance_data:
            attendance_data[emp_id] = {}

        attendance_data[emp_id][att_date] = {
            'in': check_in,
            'out': check_out,
            'status': status
        }

        if status == 'present':
            attendance_counts[emp_id]['present'] += 1
        elif status == 'late':
            attendance_counts[emp_id]['late'] += 1
        elif status == 'early':
            attendance_counts[emp_id]['early'] += 1
        elif status == 'absent':
            attendance_counts[emp_id]['absent'] += 1

    days = get_month_days(year, month)

    cursor.close()

    return render_template(
        'attendance_record.html',
        employees=employees,
        attendance_data=attendance_data,
        days=days,
        year=year,
        month=month,
        attendance_counts=attendance_counts
    )

# Save Attendance API
@app.route('/save_attendance', methods=['POST'])
def save_attendance():
    try:
        data = request.get_json()
        records = data.get('records', [])
        year = data.get('year')
        month = data.get('month')

        if not year or not month:
            return jsonify({'error': 'Year and month required'}), 400

        conn = mysql.connection
        cursor = conn.cursor()

        for rec in records:
            employee_id = rec.get('employee_id')
            date_str = rec.get('date')  # format 'YYYY-MM-DD'
            check_in_str = rec.get('check_in')  # format 'HH:MM' or None
            check_out_str = rec.get('check_out')  # format 'HH:MM' or None
            status = rec.get('status', 'present')

            if not employee_id or not date_str:
                continue

            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            # Convert check_in/out to time or None
            check_in_time = datetime.strptime(check_in_str, '%H:%M').time() if check_in_str else None
            check_out_time = datetime.strptime(check_out_str, '%H:%M').time() if check_out_str else None

            # Check if record exists
            cursor.execute("""
                SELECT id FROM attendance WHERE employee_id=%s AND attendance_date=%s
            """, (employee_id, attendance_date))
            existing = cursor.fetchone()

            if existing:
                # Update existing record
                cursor.execute("""
                    UPDATE attendance SET check_in_time=%s, check_out_time=%s, status=%s
                    WHERE id=%s
                """, (check_in_time, check_out_time, status, existing[0]))
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO attendance (employee_id, attendance_date, check_in_time, check_out_time, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (employee_id, attendance_date, check_in_time, check_out_time, status))

        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'Attendance saved successfully.'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/automated_payroll', methods=['GET', 'POST'])
def automated_payroll():
    if 'username' not in session:
        return redirect(url_for('login'))

    now = datetime.now()
    if request.method == 'POST':
        month = int(request.form.get('month', now.month))
        year = int(request.form.get('year', now.year))
    else:
        month = int(request.args.get('month', now.month))
        year = int(request.args.get('year', now.year))

    days_in_month = calendar.monthrange(year, month)[1]
    standard_in = datetime.strptime("08:10", "%H:%M").time()
    standard_out = datetime.strptime("16:30", "%H:%M").time()

    cur = mysql.connection.cursor()
    cur.execute("SELECT employee_id, fname, mname, lname, position, office FROM employee_info")
    employees = cur.fetchall()

    payroll_data = []

    for emp in employees:
        emp_id, fname, mname, lname, position, office = emp

        cur.execute("""
            SELECT attendance_date, check_in_time, check_out_time
            FROM attendance
            WHERE employee_id = %s AND MONTH(attendance_date) = %s AND YEAR(attendance_date) = %s
        """, (emp_id, month, year))
        attendance_records = cur.fetchall()

        # Map attendance by day for quick lookup
        attendance_by_day = {rec[0].day: rec for rec in attendance_records}

        total_late = 0
        total_early = 0
        total_absent = 0

        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            if current_date.weekday() >= 5:
                continue  # Skip Saturdays (5) and Sundays (6)

            rec = attendance_by_day.get(day)
            if rec:
                _, check_in, check_out = rec
                if check_in and check_in > standard_in:
                    total_late += 1
                if check_out and check_out < standard_out:
                    total_early += 1
            else:
                total_absent += 1

        record = {
            'employee_id': emp_id,
            'name': f"{lname}, {fname} {mname}",
            'position': position,
            'office': office,
            'late': total_late,
            'early': total_early,
            'absent': total_absent,
        }

        if request.method == 'POST':
            deduction = (total_absent * DEDUCTION_PER_ABSENT) + (total_late * DEDUCTION_PER_LATE) + (total_early * DEDUCTION_PER_EARLY)
            net_salary = BASE_SALARY - deduction
            record['deduction'] = deduction
            record['net_salary'] = net_salary

        payroll_data.append(record)

    cur.close()

    return render_template(
        'automated_payroll.html',
        payroll_data=payroll_data,
        username=session['username'],
        month=month,
        year=year
    )

import csv
from io import StringIO
from flask import Response

@app.route('/download_payroll')
def download_payroll():
    if 'username' not in session:
        return redirect(url_for('login'))

    month = int(request.args.get('month'))
    year = int(request.args.get('year'))

    standard_in = datetime.strptime("08:10", "%H:%M").time()
    standard_out = datetime.strptime("16:30", "%H:%M").time()
    days_in_month = calendar.monthrange(year, month)[1]

    cur = mysql.connection.cursor()
    cur.execute("SELECT employee_id, fname, mname, lname, position, office FROM employee_info")
    employees = cur.fetchall()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(['Employee ID', 'Name', 'Position', 'Office', 'Late', 'Early Leave', 'Absent', 'Deduction', 'Net Salary'])

    for emp in employees:
        emp_id, fname, mname, lname, position, office = emp

        cur.execute("""
            SELECT attendance_date, check_in_time, check_out_time
            FROM attendance
            WHERE employee_id = %s AND MONTH(attendance_date) = %s AND YEAR(attendance_date) = %s
        """, (emp_id, month, year))
        attendance_records = cur.fetchall()

        attendance_by_day = {rec[0].day: rec for rec in attendance_records}

        total_late = 0
        total_early = 0
        total_absent = 0

        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            if current_date.weekday() >= 5:
                continue  # Skip weekends

            rec = attendance_by_day.get(day)
            if rec:
                _, check_in, check_out = rec
                if check_in and check_in > standard_in:
                    total_late += 1
                if check_out and check_out < standard_out:
                    total_early += 1
            else:
                total_absent += 1

        deduction = (total_absent * DEDUCTION_PER_ABSENT) + (total_late * DEDUCTION_PER_LATE) + (total_early * DEDUCTION_PER_EARLY)
        net_salary = BASE_SALARY - deduction
        name = f"{lname}, {fname} {mname}"

        writer.writerow([emp_id, name, position, office, total_late, total_early, total_absent, f"{deduction:.2f}", f"{net_salary:.2f}"])

    cur.close()

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename=payroll_{year}_{month:02d}.csv"
    return response

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
