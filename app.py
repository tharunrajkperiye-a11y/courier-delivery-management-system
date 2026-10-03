from flask import Flask, render_template, request, redirect, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "courier-secret-key"

DATABASE = "courier.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# =========================
# DASHBOARD
# =========================

@app.route("/")
def home():

    db = get_db()

    customers = db.execute(
        "SELECT COUNT(*) FROM customer"
    ).fetchone()[0]

    employees = db.execute(
        "SELECT COUNT(*) FROM employee"
    ).fetchone()[0]

    parcels = db.execute(
        "SELECT COUNT(*) FROM parcel"
    ).fetchone()[0]

    delivered = db.execute(
        "SELECT COUNT(*) FROM parcel WHERE delivery_status = 'Delivered'"
    ).fetchone()[0]

    in_transit = db.execute(
        "SELECT COUNT(*) FROM parcel WHERE delivery_status = 'In Transit'"
    ).fetchone()[0]

    db.close()

    return render_template(
        "index.html",
        customers=customers,
        employees=employees,
        parcels=parcels,
        delivered=delivered,
        in_transit=in_transit
    )


# =========================
# ADD CUSTOMER
# =========================

@app.route("/add-customer", methods=["GET", "POST"])
def add_customer():

    if request.method == "POST":

        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        address = request.form["address"]

        db = get_db()

        db.execute(
            """
            INSERT INTO customer
            (name, phone, email, address)
            VALUES (?, ?, ?, ?)
            """,
            (name, phone, email, address)
        )

        db.commit()
        db.close()

        flash("Customer added successfully!")

        return redirect("/")


    return render_template("add_customer.html")


# =========================
# ADD EMPLOYEE
# =========================

@app.route("/add-employee", methods=["GET", "POST"])
def add_employee():

    if request.method == "POST":

        name = request.form["name"]
        phone = request.form["phone"]
        designation = request.form["designation"]

        db = get_db()

        db.execute(
            """
            INSERT INTO employee
            (name, phone, designation)
            VALUES (?, ?, ?)
            """,
            (name, phone, designation)
        )

        db.commit()
        db.close()

        flash("Employee added successfully!")

        return redirect("/")


    return render_template("add_employee.html")


# =========================
# BOOK PARCEL
# =========================

@app.route("/book-parcel", methods=["GET", "POST"])
def book_parcel():

    db = get_db()

    customers = db.execute(
        "SELECT * FROM customer ORDER BY name"
    ).fetchall()

    employees = db.execute(
        "SELECT * FROM employee ORDER BY name"
    ).fetchall()


    if request.method == "POST":

        tracking_number = request.form["tracking_number"]
        sender_id = request.form["sender_id"]
        receiver_name = request.form["receiver_name"]
        receiver_phone = request.form["receiver_phone"]
        destination = request.form["destination"]
        weight = request.form["weight"]
        booking_date = request.form["booking_date"]
        employee_id = request.form["employee_id"]


        try:

            # Insert parcel
            cursor = db.execute(
                """
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
                """,
                (
                    tracking_number,
                    sender_id,
                    receiver_name,
                    receiver_phone,
                    destination,
                    weight,
                    booking_date
                )
            )

            parcel_id = cursor.lastrowid


            # Insert first delivery log
            db.execute(
                """
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
                """,
                (
                    parcel_id,
                    employee_id,
                    "Booked",
                    booking_date,
                    "Booking Center",
                    "Parcel booked"
                )
            )

            db.commit()

            flash("Parcel booked successfully!")

            db.close()

            return redirect("/parcels")


        except sqlite3.IntegrityError:

            db.rollback()
            db.close()

            flash("Tracking number already exists!")

            return redirect("/book-parcel")


    db.close()

    return render_template(
        "book_parcel.html",
        customers=customers,
        employees=employees,
        today=date.today().isoformat()
    )


# =========================
# UPDATE DELIVERY STATUS
# =========================

@app.route("/update-status", methods=["GET", "POST"])
def update_status():

    db = get_db()

    parcels = db.execute(
        """
        SELECT parcel_id, tracking_number, delivery_status
        FROM parcel
        ORDER BY parcel_id DESC
        """
    ).fetchall()

    employees = db.execute(
        "SELECT * FROM employee ORDER BY name"
    ).fetchall()


    if request.method == "POST":

        parcel_id = request.form["parcel_id"]
        employee_id = request.form["employee_id"]
        status = request.form["status"]
        status_date = request.form["status_date"]
        location = request.form["location"]
        remarks = request.form["remarks"]


        # Update current parcel status
        db.execute(
            """
            UPDATE parcel
            SET delivery_status = ?
            WHERE parcel_id = ?
            """,
            (status, parcel_id)
        )


        # Add status to delivery history
        db.execute(
            """
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
            """,
            (
                parcel_id,
                employee_id,
                status,
                status_date,
                location,
                remarks
            )
        )


        db.commit()
        db.close()

        flash("Delivery status updated successfully!")

        return redirect("/parcels")


    db.close()

    return render_template(
        "update_status.html",
        parcels=parcels,
        employees=employees,
        today=date.today().isoformat()
    )


# =========================
# PAYMENT
# =========================

@app.route("/payment", methods=["GET", "POST"])
def payment():

    db = get_db()

    parcels = db.execute(
        """
        SELECT parcel_id, tracking_number
        FROM parcel
        ORDER BY parcel_id DESC
        """
    ).fetchall()


    if request.method == "POST":

        parcel_id = request.form["parcel_id"]
        amount = request.form["amount"]
        payment_date = request.form["payment_date"]
        payment_method = request.form["payment_method"]
        payment_status = request.form["payment_status"]


        try:

            db.execute(
                """
                INSERT INTO payment
                (
                    parcel_id,
                    amount,
                    payment_date,
                    payment_method,
                    payment_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    parcel_id,
                    amount,
                    payment_date,
                    payment_method,
                    payment_status
                )
            )

            db.commit()

            flash("Payment recorded successfully!")


        except sqlite3.IntegrityError:

            db.rollback()

            flash("Payment already exists for this parcel.")


        db.close()

        return redirect("/")


    db.close()

    return render_template(
        "payment.html",
        parcels=parcels,
        today=date.today().isoformat()
    )


# =========================
# VIEW PARCELS
# =========================

@app.route("/parcels")
def parcels():

    db = get_db()

    parcel_list = db.execute(
        """
        SELECT
            parcel.parcel_id,
            parcel.tracking_number,
            customer.name AS sender_name,
            parcel.receiver_name,
            parcel.receiver_phone,
            parcel.destination,
            parcel.weight,
            parcel.booking_date,
            parcel.delivery_status
        FROM parcel

        JOIN customer
        ON parcel.sender_id = customer.customer_id

        ORDER BY parcel.parcel_id DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "parcels.html",
        parcels=parcel_list
    )


# =========================
# VIEW DELIVERY LOGS
# =========================

@app.route("/logs")
def logs():

    db = get_db()

    log_list = db.execute(
        """
        SELECT
            delivery_log.log_id,
            parcel.tracking_number,
            employee.name AS employee_name,
            delivery_log.status,
            delivery_log.status_date,
            delivery_log.location,
            delivery_log.remarks

        FROM delivery_log

        JOIN parcel
        ON delivery_log.parcel_id = parcel.parcel_id

        JOIN employee
        ON delivery_log.employee_id = employee.employee_id

        ORDER BY delivery_log.log_id DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "logs.html",
        logs=log_list
    )


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":
    app.run(debug=True)