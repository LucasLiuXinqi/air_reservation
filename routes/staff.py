from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps
from db import get_connection
from datetime import date, timedelta

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


def staff_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("user_role") != "admin" and session.get("user_role") != "operator":
            flash("Please log in as airline staff.")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("Admin permission required.")
            return redirect(url_for("staff.dashboard"))
        return f(*args, **kwargs)
    return wrapper


def operator_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("user_role") != "operator":
            flash("Operator permission required.")
            return redirect(url_for("staff.dashboard"))
        return f(*args, **kwargs)
    return wrapper

@staff_bp.route("/dashboard", methods=["GET"])
@staff_login_required
def dashboard():
    # main dashboard: filter flights for this airline
    username = session.get("user_id")

    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to", "").strip()
    origin    = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # find staff airline
    cur.execute(
        "SELECT airline_name, first_name, last_name FROM airline_staff WHERE username = %s;",
        (username,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        flash("Could not find airline for this staff.")
        return redirect(url_for("auth.login"))

    airline_name = row["airline_name"]
    # pick up names from session first, otherwise fall back to DB and refresh the session
    first_name = session.get("firstname") or row.get("first_name")
    last_name = session.get("lastname") or row.get("last_name")
    if first_name and "firstname" not in session:
        session["firstname"] = first_name
    if last_name and "lastname" not in session:
        session["lastname"] = last_name

    # default 30 days
    if not date_from or not date_to:
        today = date.today()
        df = today
        dt = today + timedelta(days=30)
        date_from_default = df.isoformat()
        date_to_default = dt.isoformat()

        # only use defaults if user didn't type anything
        if not date_from:
            date_from = date_from_default
        if not date_to:
            date_to = date_to_default

    # query flights
    sql = """
        SELECT f.flight_num,
               f.departure_airport, f.arrival_airport,
               f.departure_time, f.arrival_time,
               f.status
        FROM flight AS f
        WHERE f.airline_name = %s
    """
    params = [airline_name]

    if date_from:
        sql += " AND f.departure_time >= %s"
        params.append(date_from + " 00:00:00")
    if date_to:
        sql += " AND f.departure_time <= %s"
        params.append(date_to + " 23:59:59")

    if origin:
        sql += " AND f.departure_airport = %s"
        params.append(origin)
    if destination:
        sql += " AND f.arrival_airport = %s"
        params.append(destination)

    sql += " ORDER BY f.departure_time;"

    cur.execute(sql, tuple(params))
    flights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "staff_dashboard.html",
        airline_name=airline_name,
        flights=flights,
        date_from=date_from,
        date_to=date_to,
        origin=origin,
        destination=destination,
        first_name=first_name,
        last_name=last_name,
    )


@staff_bp.route("/passengers", methods=["GET"])
@staff_login_required
def passengers():
    # get passengers for a specific flight
    username = session.get("user_id")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # find staff airline
    cur.execute(
        "SELECT airline_name FROM airline_staff WHERE username = %s;",
        (username,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        flash("Could not find airline for this staff.")
        return redirect(url_for("staff.dashboard"))

    airline_name = row["airline_name"]

    # read search inputs
    flight_num = request.args.get("flight_num", "").strip()
    date       = request.args.get("date", "").strip()

    passengers = []

    if flight_num:
        sql = """
            SELECT
                c.email         AS customer_email,
                c.name          AS customer_name,
                t.seat_class_id,
                p.purchase_date,
                p.purchase_price,
                f.flight_num,
                f.departure_airport,
                f.arrival_airport,
                f.departure_time,
                f.arrival_time
            FROM purchases AS p
            JOIN ticket AS t
              ON p.ticket_id = t.ticket_id
            JOIN customer AS c
              ON p.customer_email = c.email
            JOIN flight AS f
              ON t.airline_name = f.airline_name
             AND t.flight_num   = f.flight_num
            WHERE f.airline_name = %s
              AND f.flight_num   = %s
        """
        params = [airline_name, flight_num]

        if date:
            sql += " AND DATE(f.departure_time) = %s"
            params.append(date)

        sql += " ORDER BY c.name, p.purchase_date;"

        cur.execute(sql, tuple(params))
        passengers = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "staff_passengers.html",
        airline_name=airline_name,
        flight_num=flight_num,
        date=date,
        passengers=passengers,
    )
    
    
@staff_bp.route("/customer_flights", methods=["GET"])
@staff_login_required
def customer_flights():
    # get flights purchased by a specific customer
    username = session.get("user_id")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # find staff airline
    cur.execute(
        "SELECT airline_name FROM airline_staff WHERE username = %s;",
        (username,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        flash("Could not find airline for this staff.")
        return redirect(url_for("staff.dashboard"))

    airline_name = row["airline_name"]

    customer_email = request.args.get("customer_email", "").strip()
    date_from      = request.args.get("date_from", "").strip()
    date_to        = request.args.get("date_to", "").strip()

    flights = []

    if customer_email:
        sql = """
            SELECT
                f.airline_name,
                f.flight_num,
                f.departure_airport,
                f.arrival_airport,
                f.departure_time,
                f.arrival_time,
                f.status,
                t.seat_class_id,
                p.purchase_date,
                p.purchase_price
            FROM purchases AS p
            JOIN ticket AS t
              ON p.ticket_id = t.ticket_id
            JOIN flight AS f
              ON t.airline_name = f.airline_name
             AND t.flight_num   = f.flight_num
            WHERE f.airline_name   = %s
              AND p.customer_email = %s
        """
        params = [airline_name, customer_email]

        if date_from:
            sql += " AND p.purchase_date >= %s"
            params.append(date_from)
        if date_to:
            sql += " AND p.purchase_date <= %s"
            params.append(date_to)

        sql += " ORDER BY p.purchase_date DESC;"

        cur.execute(sql, tuple(params))
        flights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "staff_customer_flights.html",
        airline_name=airline_name,
        customer_email=customer_email,
        date_from=date_from,
        date_to=date_to,
        flights=flights,
    )
    
@staff_bp.route("/analytics")
@staff_login_required
def analytics():
    # airline analytics dashboard
    username = session.get("user_id")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # find staff airline
    cur.execute("SELECT airline_name FROM airline_staff WHERE username = %s;", (username,))
    row = cur.fetchone()
    if not row:
        flash("Could not find airline for this staff.")
        return redirect(url_for("staff.dashboard"))

    airline_name = row["airline_name"]

    # top booking agents
    # Last month: by tickets sold
    sql_agent_month = """
        SELECT p.booking_agent_email AS agent,
               COUNT(*) AS tickets_sold,
               SUM(p.purchase_price) * 0.10 AS commission
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        WHERE p.booking_agent_email IS NOT NULL
          AND t.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
        GROUP BY agent
        ORDER BY tickets_sold DESC
        LIMIT 5;
    """
    cur.execute(sql_agent_month, (airline_name,))
    top_agents_month = cur.fetchall()

    # Last year: by tickets sold
    sql_agent_year = """
        SELECT p.booking_agent_email AS agent,
               COUNT(*) AS tickets_sold,
               SUM(p.purchase_price) * 0.10 AS commission
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        WHERE p.booking_agent_email IS NOT NULL
          AND t.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY agent
        ORDER BY tickets_sold DESC
        LIMIT 5;
    """
    cur.execute(sql_agent_year, (airline_name,))
    top_agents_year = cur.fetchall()

    # most frequent customer
    sql_freq_cust = """
        SELECT p.customer_email AS customer,
               COUNT(*) AS flights_taken
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        WHERE t.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY customer
        ORDER BY flights_taken DESC
        LIMIT 1;
    """
    cur.execute(sql_freq_cust, (airline_name,))
    frequent_customer = cur.fetchone()

    # tickets sold per month
    sql_tickets_per_month = """
        SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') AS month,
               COUNT(*) AS tickets_sold
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        WHERE t.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        GROUP BY month
        ORDER BY month ASC;
    """
    cur.execute(sql_tickets_per_month, (airline_name,))
    tickets_per_month = cur.fetchall()

    # flight delay statistics
    sql_delay_stats = """
        SELECT 
            SUM(CASE WHEN f.status = 'delayed' THEN 1 ELSE 0 END) AS delayed_count,
            SUM(CASE WHEN f.status = 'in-progress' THEN 1 ELSE 0 END) AS ontime_count,
            SUM(CASE WHEN f.status NOT IN ('delayed','on-time') THEN 1 ELSE 0 END) AS other_count
        FROM flight AS f
        WHERE f.airline_name = %s
          AND f.departure_time >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
    """
    cur.execute(sql_delay_stats, (airline_name,))
    delay_stats = cur.fetchone()

    # top 5 destination cities
    sql_dest_3m = """
        SELECT a.airport_city AS city,
               COUNT(*) AS flights
        FROM flight f
        JOIN airport a ON f.arrival_airport = a.airport_name
        WHERE f.airline_name = %s
          AND f.departure_time >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
        GROUP BY city
        ORDER BY flights DESC
        LIMIT 5;
    """
    cur.execute(sql_dest_3m, (airline_name,))
    top_dest_3m = cur.fetchall()

    sql_dest_1y = """
        SELECT a.airport_city AS city,
               COUNT(*) AS flights
        FROM flight f
        JOIN airport a ON f.arrival_airport = a.airport_name
        WHERE f.airline_name = %s
          AND f.departure_time >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY city
        ORDER BY flights DESC
        LIMIT 5;
    """
    cur.execute(sql_dest_1y, (airline_name,))
    top_dest_1y = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "staff_analytics.html",
        airline_name=airline_name,
        top_agents_month=top_agents_month,
        top_agents_year=top_agents_year,
        frequent_customer=frequent_customer,
        tickets_per_month=tickets_per_month,
        delay_stats=delay_stats,
        top_dest_3m=top_dest_3m,
        top_dest_1y=top_dest_1y,
    )


@staff_bp.route("/admin_home", methods=["GET", "POST"])
@admin_required
def admin_home():
    # admin panel
    username = session.get("user_id")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # find staff airline
    cur.execute(
        "SELECT airline_name FROM airline_staff WHERE username = %s;",
        (username,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        flash("Could not find airline for this staff.")
        return redirect(url_for("auth.login"))

    airline_name = row["airline_name"]

    # Discover which column (if any) stores airplane seat capacity in this schema
    cur.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'airplane';
        """
    )
    airplane_cols = {r["COLUMN_NAME"] for r in cur.fetchall()}
    airplane_seat_col = next(
        (c for c in ("seat_capacity", "num_of_seats", "seats") if c in airplane_cols),
        None,
    )

    # ---------- handle POST actions ----------
    if request.method == "POST":
        form_type = request.form.get("form_type")
        try:
            # 1) Add airport
            if form_type == "airport":
                airport_name = request.form.get("airport_name", "").strip()
                airport_city = request.form.get("airport_city", "").strip()

                if not airport_name or not airport_city:
                    flash("Airport name and city are required.")
                else:
                    sql = """
                        INSERT INTO airport (airport_name, airport_city)
                        VALUES (%s, %s);
                    """
                    cur.execute(sql, (airport_name, airport_city))
                    conn.commit()
                    flash(f"Airport {airport_name} added.")

            # 2) Add airplane
            elif form_type == "airplane":
                airplane_id   = request.form.get("airplane_id", "").strip()
                seat_cap_eco  = request.form.get("seat_capacity_economy", "").strip()
                seat_cap_bus  = request.form.get("seat_capacity_business", "").strip()
                seat_cap_fst  = request.form.get("seat_capacity_first", "").strip()

                if not airplane_id or not (seat_cap_eco and seat_cap_bus and seat_cap_fst):
                    flash("Airplane ID and all three seat capacities are required.")
                else:
                    try:
                        cap_eco = int(seat_cap_eco)
                        cap_bus = int(seat_cap_bus)
                        cap_fst = int(seat_cap_fst)
                        total_capacity = cap_eco + cap_bus + cap_fst
                        if cap_eco < 0 or cap_bus < 0 or cap_fst < 0:
                            raise ValueError("Capacities must be non-negative.")
                    except ValueError:
                        flash("Seat capacities must be non-negative integers.")
                    else:
                        try:
                            if airplane_seat_col:
                                sql = f"""
                                    INSERT INTO airplane (airplane_id, airline_name, {airplane_seat_col})
                                    VALUES (%s, %s, %s);
                                """
                                cur.execute(sql, (airplane_id, airline_name, total_capacity))
                            else:
                                sql = """
                                    INSERT INTO airplane (airplane_id, airline_name)
                                    VALUES (%s, %s);
                                """
                                cur.execute(sql, (airplane_id, airline_name))

                            # insert seat_class rows for three categories
                            sql_sc = """
                                INSERT INTO seat_class (airline_name, airplane_id, seat_class_id, seat_capacity)
                                VALUES (%s, %s, %s, %s)
                                ON DUPLICATE KEY UPDATE seat_capacity = VALUES(seat_capacity);
                            """
                            cur.executemany(
                                sql_sc,
                                [
                                    (airline_name, airplane_id, 1, cap_eco),
                                    (airline_name, airplane_id, 2, cap_bus),
                                    (airline_name, airplane_id, 3, cap_fst),
                                ],
                            )

                            conn.commit()
                            flash(
                                f"Airplane {airplane_id} added for {airline_name} with seat capacities "
                                f"(economy: {cap_eco}, business: {cap_bus}, first: {cap_fst})."
                            )
                        except Exception as e:
                            conn.rollback()
                            flash(f"Failed to add airplane: {e}")

            # 3) Associate booking agent
            elif form_type == "agent":
                agent_email = request.form.get("agent_email", "").strip()

                if not agent_email:
                    flash("Agent email is required.")
                else:
                    # optional: check that booking_agent exists
                    cur.execute(
                        "SELECT email FROM booking_agent WHERE email = %s;",
                        (agent_email,)
                    )
                    if cur.fetchone() is None:
                        flash("Booking agent not found.")
                    else:
                        sql = """
                            INSERT IGNORE INTO agent_airline_authorization (agent_email, airline_name)
                            VALUES (%s, %s);
                        """
                        cur.execute(sql, (agent_email, airline_name))
                        conn.commit()
                        flash(f"Agent {agent_email} associated with {airline_name}.")

            # 4) Create flight
            elif form_type == "flight":
                flight_num        = request.form.get("flight_num", "").strip()
                departure_airport = request.form.get("departure_airport", "").strip()
                arrival_airport   = request.form.get("arrival_airport", "").strip()
                departure_time    = request.form.get("departure_time", "").strip()
                arrival_time      = request.form.get("arrival_time", "").strip()
                base_price        = request.form.get("base_price", "").strip()
                airplane_id_for_flight = request.form.get("airplane_id_for_flight", "").strip()
                status_raw        = request.form.get("status", "upcoming").strip()
                status            = "in-progress" if status_raw == "on-time" else status_raw
                allowed_statuses  = {"upcoming", "in-progress", "delayed"}

                if not (flight_num and departure_airport and arrival_airport and
                        departure_time and arrival_time and base_price and airplane_id_for_flight):
                    flash("All flight fields are required.")
                elif status not in allowed_statuses:
                    flash("Invalid status value.")
                else:
                    # datetime-local → replace 'T' with space
                    dep_sql = departure_time.replace("T", " ")
                    arr_sql = arrival_time.replace("T", " ")

                    sql = """
                        INSERT INTO flight
                            (airline_name, flight_num,
                             departure_airport, departure_time,
                             arrival_airport,   arrival_time,
                             base_price, airplane_id, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cur.execute(sql, (
                        airline_name, flight_num,
                        departure_airport, dep_sql,
                        arrival_airport,   arr_sql,
                        base_price, airplane_id_for_flight, status
                    ))
                    conn.commit()
                    flash(f"Flight {airline_name} {flight_num} created.")

        except Exception as e:
            conn.rollback()
            flash(f"Admin action failed: {e}")

    # ---------- load data to display ----------
    # all airports
    cur.execute("SELECT airport_name, airport_city FROM airport ORDER BY airport_name;")
    airports = cur.fetchall()

    # airplanes for this airline
    if airplane_seat_col:
        cur.execute(
            f"SELECT airplane_id, {airplane_seat_col} AS seat_capacity FROM airplane WHERE airline_name = %s ORDER BY airplane_id;",
            (airline_name,),
        )
    else:
        # compute total seats from seat_class when no seat column exists
        cur.execute(
            """
            SELECT a.airplane_id, COALESCE(SUM(sc.seat_capacity), 0) AS seat_capacity
            FROM airplane AS a
            LEFT JOIN seat_class AS sc
              ON sc.airline_name = a.airline_name
             AND sc.airplane_id = a.airplane_id
            WHERE a.airline_name = %s
            GROUP BY a.airplane_id
            ORDER BY a.airplane_id;
            """,
            (airline_name,),
        )
    airplanes = cur.fetchall()

    # agents associated with this airline
    cur.execute(
        "SELECT agent_email FROM agent_airline_authorization WHERE airline_name = %s;",
        (airline_name,)
    )
    agents = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "staff_admin_home.html",
        airline_name=airline_name,
        airports=airports,
        airplanes=airplanes,
        agents=agents,
        seat_col_present=bool(airplane_seat_col),
    )
    
    
@staff_bp.route("/operator_home", methods=["GET", "POST"])
@operator_required
def operator_home():
    """
    Operator panel:
      - Filter flights for this airline
      - Update flight status
    """
    username = session.get("user_id")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # find staff airline
    cur.execute(
        "SELECT airline_name FROM airline_staff WHERE username = %s;",
        (username,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        flash("Could not find airline for this staff.")
        return redirect(url_for("auth.login"))

    airline_name = row["airline_name"]

    # read filters from query string (work for both GET & POST)
    date_from   = request.args.get("date_from", "").strip()
    date_to     = request.args.get("date_to", "").strip()
    origin      = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()
    allowed_statuses = {"upcoming", "in-progress", "delayed"}

    # ----- POST: update status -----
    if request.method == "POST":
        flight_num = request.form.get("flight_num", "").strip()
        status_raw = request.form.get("status", "").strip()
        new_status = "in-progress" if status_raw == "on-time" else status_raw

        if not flight_num or not new_status:
            flash("Flight number and status are required to update.")
        elif new_status not in allowed_statuses:
            flash("Invalid status value.")
        else:
            try:
                display_status = "on-time" if new_status == "in-progress" else new_status
                sql_update = """
                    UPDATE flight
                    SET status = %s
                    WHERE airline_name = %s
                      AND flight_num = %s;
                """
                cur.execute(sql_update, (new_status, airline_name, flight_num))
                conn.commit()
                flash(f"Updated status of flight {flight_num} to '{display_status}'.")
            except Exception as e:
                conn.rollback()
                flash(f"Failed to update status: {e}")

    # ----- Query flights with filters -----
    sql = """
        SELECT f.flight_num,
               f.departure_airport, f.arrival_airport,
               f.departure_time, f.arrival_time,
               f.status
        FROM flight AS f
        WHERE f.airline_name = %s
    """
    params = [airline_name]

    if date_from:
        sql += " AND f.departure_time >= %s"
        params.append(date_from + " 00:00:00")
    if date_to:
        sql += " AND f.departure_time <= %s"
        params.append(date_to + " 23:59:59")
    if origin:
        sql += " AND f.departure_airport = %s"
        params.append(origin)
    if destination:
        sql += " AND f.arrival_airport = %s"
        params.append(destination)

    sql += " ORDER BY f.departure_time DESC LIMIT 200;"

    cur.execute(sql, tuple(params))
    flights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "staff_operator_home.html",
        airline_name=airline_name,
        flights=flights,
        date_from=date_from,
        date_to=date_to,
        origin=origin,
        destination=destination,
    )
