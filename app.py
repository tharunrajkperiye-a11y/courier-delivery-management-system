import os, sqlite3
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-dev-only-change-this")
DATABASE = os.environ.get("DATABASE_PATH", "courier.db")

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def init_db():
    db = get_db()
    if os.path.exists("schema.sql"):
        with open("schema.sql", encoding="utf-8") as f:
            db.executescript(f.read())
    db.executescript("""
    CREATE TABLE IF NOT EXISTS app_user(
      user_id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('admin','staff','customer')),
      customer_id INTEGER UNIQUE,
      employee_id INTEGER UNIQUE,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(customer_id) REFERENCES customer(customer_id),
      FOREIGN KEY(employee_id) REFERENCES employee(employee_id)
    );""")
    au, ap = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
    if au and ap and not db.execute("SELECT 1 FROM app_user WHERE username=?", (au,)).fetchone():
        db.execute("INSERT INTO app_user(username,password_hash,role) VALUES(?,?, 'admin')",
                   (au, generate_password_hash(ap)))
    db.commit()
    db.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*a, **kw):
        if not session.get("user_id"):
            flash("Please log in to continue.")
            return redirect(url_for("login", next=request.path))
        return fn(*a, **kw)
    return wrapped

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapped(*a, **kw):
            if session.get("role") not in roles:
                flash("You do not have permission to access that page.")
                return redirect(url_for("home"))
            return fn(*a, **kw)
        return wrapped
    return deco

@app.route("/login", methods=["GET","POST"])
def login():
    if session.get("user_id"): return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        db = get_db()
        user = db.execute("SELECT * FROM app_user WHERE username=?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            for key in ("user_id","username","role","customer_id","employee_id"):
                session[key] = user[key]
            dest = request.args.get("next","")
            if not dest.startswith("/") or dest.startswith("//"): dest = url_for("home")
            return redirect(dest)
        flash("Incorrect username or password.")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))

@app.route("/register-customer", methods=["GET","POST"])
def register_customer():
    if request.method == "POST":
        name=request.form.get("name","").strip(); phone=request.form.get("phone","").strip()
        email=request.form.get("email","").strip(); address=request.form.get("address","").strip()
        username=request.form.get("username","").strip(); password=request.form.get("password","")
        if not all([name,phone,username,password]) or len(password)<8:
            flash("Name, phone and username are required; password must be at least 8 characters.")
            return render_template("register_customer.html")
        db=get_db()
        try:
            cur=db.execute("INSERT INTO customer(name,phone,email,address) VALUES(?,?,?,?)",(name,phone,email,address))
            db.execute("INSERT INTO app_user(username,password_hash,role,customer_id) VALUES(?,?, 'customer',?)",
                       (username,generate_password_hash(password),cur.lastrowid))
            db.commit(); flash("Account created. You can now log in."); return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            db.rollback(); flash("That username is already in use.")
        finally: db.close()
    return render_template("register_customer.html")

@app.route("/")
@login_required
def home():
    if session["role"]=="customer": return redirect(url_for("customer_dashboard"))
    db=get_db()
    stats=[db.execute("SELECT COUNT(*) FROM customer").fetchone()[0],
           db.execute("SELECT COUNT(*) FROM employee").fetchone()[0],
           db.execute("SELECT COUNT(*) FROM parcel").fetchone()[0],
           db.execute("SELECT COUNT(*) FROM parcel WHERE delivery_status='Delivered'").fetchone()[0],
           db.execute("SELECT COUNT(*) FROM parcel WHERE delivery_status='In Transit'").fetchone()[0]]
    db.close()
    return render_template("index.html",customers=stats[0],employees=stats[1],parcels=stats[2],delivered=stats[3],in_transit=stats[4])

@app.route("/customer")
@roles_required("customer")
def customer_dashboard():
    db=get_db()
    parcels=db.execute("""SELECT tracking_number,receiver_name,destination,weight,booking_date,delivery_status
      FROM parcel WHERE sender_id=? ORDER BY parcel_id DESC""",(session["customer_id"],)).fetchall()
    db.close()
    return render_template("customer_dashboard.html",parcels=parcels)

@app.route("/add-customer",methods=["GET","POST"])
@roles_required("admin","staff")
def add_customer():
    if request.method=="POST":
        db=get_db(); db.execute("INSERT INTO customer(name,phone,email,address) VALUES(?,?,?,?)",
          (request.form["name"],request.form["phone"],request.form.get("email",""),request.form.get("address","")))
        db.commit(); db.close(); flash("Customer added successfully!"); return redirect(url_for("home"))
    return render_template("add_customer.html")

@app.route("/add-employee",methods=["GET","POST"])
@roles_required("admin")
def add_employee():
    if request.method=="POST":
        password=request.form["password"]
        if len(password)<8:
            flash("Password must be at least 8 characters."); return render_template("add_employee.html")
        db=get_db()
        try:
            cur=db.execute("INSERT INTO employee(name,phone,designation) VALUES(?,?,?)",
              (request.form["name"],request.form["phone"],request.form["designation"]))
            db.execute("INSERT INTO app_user(username,password_hash,role,employee_id) VALUES(?,?, 'staff',?)",
              (request.form["username"].strip(),generate_password_hash(password),cur.lastrowid))
            db.commit(); flash("Employee and staff login created."); return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            db.rollback(); flash("Username already exists.")
        finally: db.close()
    return render_template("add_employee.html")

@app.route("/book-parcel",methods=["GET","POST"])
@roles_required("admin","staff")
def book_parcel():
    db=get_db(); customers=db.execute("SELECT * FROM customer ORDER BY name").fetchall()
    employees=db.execute("SELECT * FROM employee ORDER BY name").fetchall()
    if request.method=="POST":
        try:
            cur=db.execute("""INSERT INTO parcel(tracking_number,sender_id,receiver_name,receiver_phone,destination,weight,booking_date,delivery_status)
              VALUES(?,?,?,?,?,?,?,'Booked')""",(request.form["tracking_number"],request.form["sender_id"],request.form["receiver_name"],
              request.form["receiver_phone"],request.form["destination"],request.form["weight"],request.form["booking_date"]))
            db.execute("""INSERT INTO delivery_log(parcel_id,employee_id,status,status_date,location,remarks)
              VALUES(?,?,'Booked',?,'Booking Center','Parcel booked')""",(cur.lastrowid,request.form["employee_id"],request.form["booking_date"]))
            db.commit(); flash("Parcel booked successfully!"); return redirect(url_for("parcels"))
        except sqlite3.IntegrityError:
            db.rollback(); flash("Could not book parcel. Check tracking number and selected records.")
        finally: db.close()
        return redirect(url_for("book_parcel"))
    db.close(); return render_template("book_parcel.html",customers=customers,employees=employees,today=date.today().isoformat())

@app.route("/update-status",methods=["GET","POST"])
@roles_required("admin","staff")
def update_status():
    db=get_db(); parcels=db.execute("SELECT parcel_id,tracking_number,delivery_status FROM parcel ORDER BY parcel_id DESC").fetchall()
    employees=db.execute("SELECT * FROM employee ORDER BY name").fetchall()
    if request.method=="POST":
        try:
            db.execute("UPDATE parcel SET delivery_status=? WHERE parcel_id=?",(request.form["status"],request.form["parcel_id"]))
            db.execute("""INSERT INTO delivery_log(parcel_id,employee_id,status,status_date,location,remarks)
              VALUES(?,?,?,?,?,?)""",(request.form["parcel_id"],request.form["employee_id"],request.form["status"],
              request.form["status_date"],request.form["location"],request.form.get("remarks","")))
            db.commit(); flash("Delivery status updated.")
        except sqlite3.IntegrityError:
            db.rollback(); flash("Could not update status. Check selected parcel and employee.")
        finally: db.close()
        return redirect(url_for("parcels"))
    db.close(); return render_template("update_status.html",parcels=parcels,employees=employees,today=date.today().isoformat())

@app.route("/payment",methods=["GET","POST"])
@roles_required("admin")
def payment():
    db=get_db(); parcels=db.execute("SELECT parcel_id,tracking_number FROM parcel ORDER BY parcel_id DESC").fetchall()
    if request.method=="POST":
        try:
            db.execute("INSERT INTO payment(parcel_id,amount,payment_date,payment_method,payment_status) VALUES(?,?,?,?,?)",
              (request.form["parcel_id"],request.form["amount"],request.form["payment_date"],request.form["payment_method"],request.form["payment_status"]))
            db.commit(); flash("Payment recorded.")
        except sqlite3.IntegrityError:
            db.rollback(); flash("Payment already exists for this parcel or parcel is invalid.")
        finally: db.close()
        return redirect(url_for("home"))
    db.close(); return render_template("payment.html",parcels=parcels,today=date.today().isoformat())

@app.route("/parcels")
@roles_required("admin","staff")
def parcels():
    db=get_db(); rows=db.execute("""SELECT p.parcel_id,p.tracking_number,c.name AS sender_name,p.receiver_name,p.receiver_phone,
      p.destination,p.weight,p.booking_date,p.delivery_status FROM parcel p JOIN customer c ON p.sender_id=c.customer_id
      ORDER BY p.parcel_id DESC""").fetchall(); db.close()
    return render_template("parcels.html",parcels=rows)

@app.route("/logs")
@roles_required("admin","staff")
def logs():
    db=get_db(); rows=db.execute("""SELECT l.log_id,p.tracking_number,e.name AS employee_name,l.status,l.status_date,l.location,l.remarks
      FROM delivery_log l JOIN parcel p ON l.parcel_id=p.parcel_id JOIN employee e ON l.employee_id=e.employee_id
      ORDER BY l.log_id DESC""").fetchall(); db.close()
    return render_template("logs.html",logs=rows)

init_db()
if __name__=="__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG")=="1")
