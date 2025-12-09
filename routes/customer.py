from decimal import Decimal
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from datetime import datetime
from mysql.connector import Error
from functools import wraps
from db import get_connection

customer_bp = Blueprint("customer", __name__)

def customer_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_role") != "customer":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


@customer_bp.route("/")
def index():
    return render_template("index.html")

@customer_bp.route("/dashboard")
@customer_login_required    #ensure only logged-in customers can access
def dashboard():
    email = session.get("user_email")

    # filters from query string
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to", "").strip()
    origin    = request.args.get("origin", "").strip()
    dest      = request.args.get("dest", "").strip()
    show_all  = request.args.get("show_all", "0")  # "0" or "1"

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    sql = """
        SELECT f.airline_name, f.flight_num,
               f.departure_airport, f.arrival_airport,
               f.departure_time, f.arrival_time, f.status
        FROM purchases AS p
        JOIN ticket AS t
          ON p.ticket_id = t.ticket_id
        JOIN flight AS f
          ON t.airline_name = f.airline_name
         AND t.flight_num   = f.flight_num
        JOIN airport AS a_dep
          ON f.departure_airport = a_dep.airport_name
        JOIN airport AS a_arr
          ON f.arrival_airport   = a_arr.airport_name
        WHERE p.customer_email = %s
    """
    params = [email]

    # upcoming vs all
    if show_all != "1":
        sql += " AND f.departure_time >= NOW()"

    # date range filters
    if date_from:
        sql += " AND DATE(f.departure_time) >= %s"
        params.append(date_from)

    if date_to:
        sql += " AND DATE(f.departure_time) <= %s"
        params.append(date_to)

    # origin filter (match by airport_name or city)
    if origin:
        sql += " AND (a_dep.airport_name = %s OR a_dep.airport_city = %s)"
        params.extend([origin, origin])

    # destination filter
    if dest:
        sql += " AND (a_arr.airport_name = %s OR a_arr.airport_city = %s)"
        params.extend([dest, dest])

    sql += " ORDER BY f.departure_time DESC"

    cur.execute(sql, tuple(params))
    flights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "customer_dashboard.html",
        flights=flights,
        date_from=date_from,
        date_to=date_to,
        origin=origin,
        dest=dest,
        show_all=show_all,
    )
    


@customer_bp.route("/purchase", methods=["POST"])
@customer_login_required
def purchase():
    customer_email = session.get("user_email")

    # Values from the form in search_results.html
    airline_name  = request.form.get("airline_name", "").strip()
    flight_num    = request.form.get("flight_num", "").strip()
    airplane_id   = request.form.get("airplane_id", "").strip()
    seat_class_id = request.form.get("seat_class_id", "").strip()

    # Search filters
    origin      = request.form.get("origin", "").strip()
    destination = request.form.get("destination", "").strip()
    date        = request.form.get("date", "").strip()

    # Helper: go back to the same search results
    def back_to_search():
        return redirect(url_for(
            "search_flights.search_flights",
            origin=origin,
            destination=destination,
            date=date
        ))

    # Basic validation
    if not (airline_name and flight_num and airplane_id and seat_class_id):
        flash("Missing purchase information.")
        return back_to_search()

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # 1) Get seat capacity for this flight + seat class
        sql_capacity = """
            SELECT sc.seat_capacity
            FROM seat_class AS sc
            JOIN flight AS f
              ON sc.airline_name = f.airline_name
             AND sc.airplane_id  = f.airplane_id
            WHERE f.airline_name   = %s
              AND f.flight_num     = %s
              AND sc.seat_class_id = %s
        """
        cur.execute(sql_capacity, (airline_name, flight_num, seat_class_id))
        row = cur.fetchone()
        if not row:
            flash("Seat class not found for this flight.")
            return back_to_search()

        seat_capacity = row["seat_capacity"]

        # 2) Count tickets already sold for this flight + class
        sql_sold = """
            SELECT COUNT(*) AS sold
            FROM ticket AS t
            JOIN purchases AS p
              ON t.ticket_id = p.ticket_id
            WHERE t.airline_name  = %s
              AND t.flight_num    = %s
              AND t.seat_class_id = %s
        """
        cur.execute(sql_sold, (airline_name, flight_num, seat_class_id))
        sold = cur.fetchone()["sold"]

        if sold >= seat_capacity:
            flash("Sorry, this class is fully booked for that flight.")
            return back_to_search()

        # 3) Get base price for the flight (and ensure it is not in the past)
        sql_price = """
            SELECT base_price, departure_time
            FROM flight
            WHERE airline_name = %s
              AND flight_num   = %s
        """
        cur.execute(sql_price, (airline_name, flight_num))
        row = cur.fetchone()
        if not row:
            flash("Flight not found.")
            return back_to_search()

        # prevent purchasing for past flights
        if row["departure_time"] < datetime.now():
            flash("Cannot purchase a ticket for a past flight.")
            return back_to_search()

        base_price = row["base_price"]

        # 4) Prevent multiple tickets for the same flight (any class) by this customer
        cur.execute(
            """
            SELECT 1
            FROM ticket AS t
            JOIN purchases AS p ON t.ticket_id = p.ticket_id
            WHERE p.customer_email = %s
              AND t.airline_name   = %s
              AND t.flight_num     = %s
            LIMIT 1
            """,
            (customer_email, airline_name, flight_num),
        )
        if cur.fetchone():
            flash("You already have a ticket for this flight.")
            return back_to_search()

        # 5) Compute purchase_price based on seat class
        seat_class_id_int = int(seat_class_id)
        if seat_class_id_int == 1:      # Economy
            factor = Decimal("1.0")
        elif seat_class_id_int == 2:    # Business
            factor = Decimal("1.5")
        else:                           # First
            factor = Decimal("2.0")

        purchase_price = int(Decimal(str(base_price)) * factor)

        # 6) Insert a ticket with an explicit ticket_id (table has no auto_increment)
        cur.execute("SELECT COALESCE(MAX(ticket_id), 0) + 1 AS next_id FROM ticket")
        next_ticket_id = cur.fetchone()["next_id"]
        sql_insert_ticket = """
            INSERT INTO ticket (ticket_id, airline_name, flight_num, airplane_id, seat_class_id)
            VALUES (%s, %s, %s, %s, %s)
        """
        cur.execute(sql_insert_ticket,
                    (next_ticket_id, airline_name, flight_num, airplane_id, seat_class_id))
        ticket_id = next_ticket_id   # ticket_id is manually assigned

        # 6) Insert into purchases
        sql_insert_purchase = """
            INSERT INTO purchases
                (ticket_id, customer_email, booking_agent_email, purchase_date, purchase_price)
            VALUES
                (%s, %s, %s, CURDATE(), %s)
        """
        cur.execute(sql_insert_purchase,
                    (ticket_id, customer_email, None, purchase_price))

        conn.commit()
        flash(f"Ticket purchased successfully for {airline_name} flight {flight_num} "
              f"in class {seat_class_id}. Price: {purchase_price}")
        return redirect(url_for("search_flights.search_flights"))

    except Exception as e:
        conn.rollback()
        flash(f"Purchase failed: {e}")
        return back_to_search()
    finally:
        cur.close()
        conn.close()


@customer_bp.route("/spending", methods=["GET"])
@customer_login_required
def spending():
    email = session.get("user_email")

    # Custom range parameters (optional)
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to", "").strip()

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # last 12 months total
    sql_total_12 = """
        SELECT IFNULL(SUM(purchase_price), 0) AS total_12
        FROM purchases
        WHERE customer_email = %s
          AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
    """
    cur.execute(sql_total_12, (email,))
    total_12 = cur.fetchone()["total_12"]

    # last 6 months by month
    sql_6_months = """
        SELECT DATE_FORMAT(purchase_date, '%Y-%m') AS ym,
               SUM(purchase_price) AS total
        FROM purchases
        WHERE customer_email = %s
          AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY ym
        ORDER BY ym
    """
    cur.execute(sql_6_months, (email,))
    rows_6 = cur.fetchall()

    # Build the last 6 calendar months labels in order (oldest -> newest)
    def shift_month(dt, delta):
        year = dt.year + (dt.month - 1 + delta) // 12
        month = (dt.month - 1 + delta) % 12 + 1
        return dt.replace(year=year, month=month, day=1)

    today = datetime.today().replace(day=1)
    last6_labels = [shift_month(today, offset).strftime("%Y-%m") for offset in range(-5, 1)]
    last6_map = {row["ym"]: float(row["total"]) for row in rows_6}
    last6_values = [last6_map.get(label, 0.0) for label in last6_labels]

    # custom range by month
    custom_total = None
    custom_labels = []
    custom_values = []

    if date_from and date_to:
        sql_custom = """
            SELECT DATE_FORMAT(purchase_date, '%Y-%m') AS ym,
                   SUM(purchase_price) AS total
            FROM purchases
            WHERE customer_email = %s
              AND purchase_date BETWEEN %s AND %s
            GROUP BY ym
            ORDER BY ym
        """
        cur.execute(sql_custom, (email, date_from, date_to))
        custom_rows = cur.fetchall()

        custom_labels = [row["ym"] for row in custom_rows]
        custom_values = [float(row["total"]) for row in custom_rows]

        # total over custom range
        sql_custom_total = """
            SELECT IFNULL(SUM(purchase_price), 0) AS total_custom
            FROM purchases
            WHERE customer_email = %s
              AND purchase_date BETWEEN %s AND %s
        """
        cur.execute(sql_custom_total, (email, date_from, date_to))
        custom_total = float(cur.fetchone()["total_custom"])

    cur.close()
    conn.close()

    return render_template(
        "customer_spending.html",
        total_12=float(total_12),
        last6_labels=last6_labels,
        last6_values=last6_values,
        date_from=date_from,
        date_to=date_to,
        custom_total=custom_total,
        custom_labels=custom_labels,
        custom_values=custom_values,
    )


@customer_bp.route("/profile", methods=["GET", "POST"])
@customer_login_required
def profile():
    email = session.get("user_email")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        # Read form values
        name               = request.form.get("name", "").strip()
        building_number    = request.form.get("building_number", "").strip()
        street             = request.form.get("street", "").strip()
        city               = request.form.get("city", "").strip()
        state              = request.form.get("state", "").strip()
        phone_number       = request.form.get("phone_number", "").strip()
        passport_number    = request.form.get("passport_number", "").strip()
        passport_exp       = request.form.get("passport_expiration", "").strip()
        passport_country   = request.form.get("passport_country", "").strip()
        date_of_birth      = request.form.get("date_of_birth", "").strip()

        try:
            sql_update = """
                UPDATE customer
                SET name = %s,
                    building_number = %s,
                    street = %s,
                    city = %s,
                    state = %s,
                    phone_number = %s,
                    passport_number = %s,
                    passport_expiration = %s,
                    passport_country = %s,
                    date_of_birth = %s
                WHERE email = %s
            """
            params = (
                name, building_number, street, city, state,
                phone_number, passport_number, passport_exp,
                passport_country, date_of_birth, email
            )
            cur.execute(sql_update, params)
            conn.commit()

            # Update name in session so navbar/dashboard reflect change
            session["user_name"] = name

            flash("Profile updated successfully.")
            # After POST, redirect (PRG pattern)
            return redirect(url_for("customer.profile"))

        except Exception as e:
            conn.rollback()
            flash(f"Failed to update profile: {e}")
            # fall through to re-fetch and re-render

    # GET (or after failed POST): fetch current data
    cur.execute("SELECT * FROM customer WHERE email = %s", (email,))
    customer = cur.fetchone()

    cur.close()
    conn.close()

    if not customer:
        flash("Customer record not found.")
        return redirect(url_for("customer.index"))

    return render_template("customer_profile.html", customer=customer)
