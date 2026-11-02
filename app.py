
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, flash, session, url_for
)

app = Flask(__name__)

# Project paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.secret_key = os.environ.get(
    "SECRET_KEY", "change-this-local-secret"
)

DATABASE = os.environ.get(
    "DATABASE_PATH",
    os.path.join(BASE_DIR, "courier.db")
)

SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")

# Admin credentials
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


# ---------------- DATABASE INITIALIZATION ----------------

def init_db():
    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError("schema.sql file not found!")

    db = get_db()

    with open(SCHEMA_FILE, "r", encoding="utf-8") as file:
        schema = file.read()

    db.executescript(schema)
    db.commit()
    db.close()

    print("CourierFlow database initialized successfully!")


# IMPORTANT:
# This runs when Render/Gunicorn imports app.py.
init_db()


# ---------------- ADMIN LOGIN PROTECTION ----------------

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in as Admin.")
            return redirect(url_for("login"))

        return fn(*args, **kwargs)

    return wrapper


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("admin_logged_in"):
        return redirect(url_for("home"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:

            session.clear()
            session["admin_logged_in"] = True
            session["username"] = username

            return redirect(url_for("home"))

        flash("Incorrect Admin username or password.")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout", methods=["POST"])
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("login"))


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/")
@admin_required
def home():

    db = get_db()

    # Customer records
    customers = db.execute("""
        SELECT *
        FROM customer
        ORDER BY customer_id DESC
    """).fetchall()

    # Employee records
    employees = db.execute("""
        SELECT *
        FROM employee
        ORDER BY employee_id DESC
    """).fetchall()

    # Parcel records with customer names
    parcels = db.execute("""
        SELECT p.*, c.name AS sender_name
        FROM parcel p
        JOIN customer c
        ON p.sender_id = c.customer_id
        ORDER BY p.parcel_id DESC
    """).fetchall()

    # Payment records with tracking numbers
    payments = db.execute("""
        SELECT pay.*, p.tracking_number
        FROM payment pay
        JOIN parcel p
        ON pay.parcel_id = p.parcel_id
        ORDER BY pay.payment_id DESC
    """).fetchall()

    # Delivery log records with employee names
    logs = db.execute("""
        SELECT l.*, p.tracking_number,
               e.name AS employee_name
        FROM delivery_log l
        JOIN parcel p ON l.parcel_id = p.parcel_id
        JOIN employee e ON l.employee_id = e.employee_id
        ORDER BY l.log_id DESC
    """).fetchall()

    # Dashboard counts
    stats = {
        "customers": len(customers),
        "employees": len(employees),
        "parcels": len(parcels),
        "payments": len(payments),
        "logs": len(logs),

        "delivered": db.execute("""
            SELECT COUNT(*)
            FROM parcel
            WHERE delivery_status = 'Delivered'
        """).fetchone()[0]
    }

    db.close()

    return render_template(
        "index.html",
        stats=stats,
        customers=customers,
        employees=employees,
        parcels=parcels,
        payments=payments,
        logs=logs
    )


# ---------------- ADD CUSTOMER ----------------

@app.route("/add-customer", methods=["GET", "POST"])
@admin_required
def add_customer():

    if request.method == "POST":

        db = get_db()

        db.execute("""
            INSERT INTO customer
            (name, phone, email, address)
            VALUES (?, ?, ?, ?)
        """, (
            request.form["name"],
            request.form["phone"],
            request.form.get("email", ""),
            request.form.get("address", "")
        ))

        db.commit()
        db.close()

        flash("Customer added successfully.")

        return redirect(url_for("home"))

    return render_template("add_customer.html")


# ---------------- ADD EMPLOYEE ----------------

@app.route("/add-employee", methods=["GET", "POST"])
@admin_required
def add_employee():

    if request.method == "POST":

        db = get_db()

        db.execute("""
            INSERT INTO employee
            (name, phone, designation)
            VALUES (?, ?, ?)
        """, (
            request.form["name"],
            request.form["phone"],
            request.form["designation"]
        ))

        db.commit()
        db.close()

        flash("Employee added successfully.")

        return redirect(url_for("home"))

    return render_template("add_employee.html")


# ---------------- BOOK PARCEL ----------------

@app.route("/book-parcel", methods=["GET", "POST"])
@admin_required
def book_parcel():

    db = get_db()

    customers = db.execute("""
        SELECT * FROM customer ORDER BY name
    """).fetchall()

    employees = db.execute("""
        SELECT * FROM employee ORDER BY name
    """).fetchall()

    if request.method == "POST":

        try:

            cursor = db.execute("""
                INSERT INTO parcel
                (
                    tracking_number,
                    sender_id,
                    receiver_name,
                    receiver_phone,
                    destination,
                    weight,
                    booking_date,
                    delivery_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Booked')
            """, (
                request.form["tracking_number"],
                request.form["sender_id"],
                request.form["receiver_name"],
                request.form["receiver_phone"],
                request.form["destination"],
                request.form["weight"],
                request.form["booking_date"]
            ))

            parcel_id = cursor.lastrowid

            # Create initial delivery log
            db.execute("""
                INSERT INTO delivery_log
                (
                    parcel_id,
                    employee_id,
                    status,
                    status_date,
                    location,
                    remarks
                )
                VALUES (?, ?, 'Booked', ?, 'Booking Center', 'Parcel booked')
            """, (
                parcel_id,
                request.form["employee_id"],
                request.form["booking_date"]
            ))

            db.commit()

            flash("Parcel booked successfully.")

            db.close()

            return redirect(url_for("home"))

        except sqlite3.Error:

            db.rollback()
            db.close()

            flash("Could not book parcel. Check the entered details.")

            return redirect(url_for("book_parcel"))

    db.close()

    return render_template(
        "book_parcel.html",
        customers=customers,
        employees=employees,
        today=date.today().isoformat()
    )


# ---------------- UPDATE PARCEL STATUS ----------------

@app.route("/update-status", methods=["GET", "POST"])
@admin_required
def update_status():

    db = get_db()

    parcels = db.execute("""
        SELECT parcel_id, tracking_number, delivery_status
        FROM parcel
        ORDER BY parcel_id DESC
    """).fetchall()

    employees = db.execute("""
        SELECT * FROM employee ORDER BY name
    """).fetchall()

    if request.method == "POST":

        try:

            db.execute("""
                UPDATE parcel
                SET delivery_status = ?
                WHERE parcel_id = ?
            """, (
                request.form["status"],
                request.form["parcel_id"]
            ))

            db.execute("""
                INSERT INTO delivery_log
                (
                    parcel_id,
                    employee_id,
                    status,
                    status_date,
                    location,
                    remarks
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request.form["parcel_id"],
                request.form["employee_id"],
                request.form["status"],
                request.form["status_date"],
                request.form["location"],
                request.form.get("remarks", "")
            ))

            db.commit()

            flash("Parcel status updated successfully.")

        except sqlite3.Error:

            db.rollback()

            flash("Could not update parcel status.")

        db.close()

        return redirect(url_for("home"))

    db.close()

    return render_template(
        "update_status.html",
        parcels=parcels,
        employees=employees,
        today=date.today().isoformat()
    )


# ---------------- PAYMENT MANAGEMENT ----------------

@app.route("/payment", methods=["GET", "POST"])
@admin_required
def payment():

    db = get_db()

    parcels = db.execute("""
        SELECT parcel_id, tracking_number
        FROM parcel
        ORDER BY parcel_id DESC
    """).fetchall()

    if request.method == "POST":

        try:

            db.execute("""
                INSERT INTO payment
                (
                    parcel_id,
                    amount,
                    payment_date,
                    payment_method,
                    payment_status
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                request.form["parcel_id"],
                request.form["amount"],
                request.form["payment_date"],
                request.form["payment_method"],
                request.form["payment_status"]
            ))

            db.commit()

            flash("Payment recorded successfully.")

        except sqlite3.Error:

            db.rollback()

            flash("Could not record payment. Check if payment already exists.")

        db.close()

        return redirect(url_for("home"))

    db.close()

    return render_template(
        "payment.html",
        parcels=parcels,
        today=date.today().isoformat()
    )


# ---------------- PARCEL LIST ----------------

@app.route("/parcels")
@admin_required
def parcels():

    db = get_db()

    rows = db.execute("""
        SELECT
            p.parcel_id,
            p.tracking_number,
            c.name AS sender_name,
            p.receiver_name,
            p.receiver_phone,
            p.destination,
            p.weight,
            p.booking_date,
            p.delivery_status
        FROM parcel p
        JOIN customer c
        ON p.sender_id = c.customer_id
        ORDER BY p.parcel_id DESC
    """).fetchall()

    db.close()

    return render_template("parcels.html", parcels=rows)


# ---------------- DELIVERY LOGS ----------------

@app.route("/logs")
@admin_required
def logs():

    db = get_db()

    rows = db.execute("""
        SELECT
            l.log_id,
            p.tracking_number,
            e.name AS employee_name,
            l.status,
            l.status_date,
            l.location,
            l.remarks
        FROM delivery_log l
        JOIN parcel p
        ON l.parcel_id = p.parcel_id
        JOIN employee e
        ON l.employee_id = e.employee_id
        ORDER BY l.log_id DESC
    """).fetchall()

    db.close()

    return render_template("logs.html", logs=rows)


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":

    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
