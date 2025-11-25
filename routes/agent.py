from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps
from decimal import Decimal
from db import get_connection
from datetime import datetime

agent_bp = Blueprint("agent", __name__, url_prefix="/agent")


def agent_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("user_role") != "agent":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


@agent_bp.route("/dashboard", methods=["GET"])
@agent_login_required
def dashboard():
    # view flights
    agent_email = session.get("user_email")

    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to", "").strip()
    origin    = request.args.get("origin", "").strip()
    dest      = request.args.get("dest", "").strip()

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    sql = """
        SELECT f.airline_name, f.flight_num,
               f.departure_airport, f.arrival_airport,
               f.departure_time, f.arrival_time,
               f.status,
               p.customer_email,
               p.purchase_date,
               p.purchase_price,
               a_dep.airport_city AS origin_city,
               a_arr.airport_city AS dest_city
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
        WHERE p.booking_agent_email = %s
    """
    params = [agent_email]

    if date_from:
        sql += " AND p.purchase_date >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND p.purchase_date <= %s"
        params.append(date_to)

    if origin:
        sql += " AND (a_dep.airport_name = %s OR a_dep.airport_city = %s)"
        params.extend([origin, origin])
    if dest:
        sql += " AND (a_arr.airport_name = %s OR a_arr.airport_city = %s)"
        params.extend([dest, dest])

    sql += " ORDER BY p.purchase_date DESC"

    cur.execute(sql, tuple(params))
    flights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "agent_dashboard.html",
        flights=flights,
        date_from=date_from,
        date_to=date_to,
        origin=origin,
        dest=dest,
    )
    
    

@agent_bp.route('/purchase', methods=['POST'])
@agent_login_required
def purchase():
    agent_email = session.get("user_email") 

    # flight info from the form
    airline_name   = request.form.get('airline_name', "").strip()
    flight_num     = request.form.get('flight_num', "").strip()
    airplane_id    = request.form.get('airplane_id', "").strip()
    seat_class_id  = request.form.get('seat_class_id', "").strip()
    customer_email = request.form.get('customer_email', "").strip()

    # keep search filters so we can go back to the same results
    origin      = request.form.get('origin', "")
    destination = request.form.get('destination', "")
    date        = request.form.get('date', "")

    def back_to_search():
        return redirect(url_for(
            'search_flights.search_flights',
            origin=origin,
            destination=destination,
            date=date
        ))

    # basic validation
    if not (airline_name and flight_num and airplane_id and seat_class_id and customer_email):
        flash("Missing purchase information.", "error")
        return back_to_search()

    try:
        seat_class_int = int(seat_class_id)
    except ValueError:
        flash("Invalid seat class selected.", "error")
        return back_to_search()
    if seat_class_int not in (1, 2, 3):
        flash("Invalid seat class selected.", "error")
        return back_to_search()

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # 1) customer must exist
        cur.execute("SELECT 1 FROM customer WHERE email = %s", (customer_email,))
        if not cur.fetchone():
            flash("Purchase failed: customer does not exist.", "error")
            return back_to_search()

        # 2) ensure flight exists and is not in the past
        cur.execute(
            """
            SELECT base_price, departure_time
            FROM flight
            WHERE airline_name = %s
              AND flight_num   = %s
              AND airplane_id  = %s
            """,
            (airline_name, flight_num, airplane_id)
        )
        flight = cur.fetchone()
        if not flight:
            flash("Purchase failed: flight not found.", "error")
            return back_to_search()
        if flight["departure_time"] < datetime.now():
            flash("Purchase failed: this flight has already departed.", "error")
            return back_to_search()

        # 3) seat class capacity for this flight
        cur.execute(
            """
            SELECT sc.seat_capacity
            FROM seat_class AS sc
            JOIN flight AS f
              ON sc.airline_name = f.airline_name
             AND sc.airplane_id  = f.airplane_id
            WHERE f.airline_name   = %s
              AND f.flight_num     = %s
              AND sc.seat_class_id = %s
            """,
            (airline_name, flight_num, seat_class_id)
        )
        row = cur.fetchone()
        if not row:
            flash("Purchase failed: seat class not found for this flight.", "error")
            return back_to_search()
        seat_capacity = row["seat_capacity"]

        # 4) prevent duplicate purchase for same customer/flight/class
        cur.execute(
            """
            SELECT 1
            FROM ticket AS t
            JOIN purchases AS p ON t.ticket_id = p.ticket_id
            WHERE t.airline_name  = %s
              AND t.flight_num    = %s
              AND t.seat_class_id = %s
              AND p.customer_email = %s
            LIMIT 1
            """,
            (airline_name, flight_num, seat_class_id, customer_email)
        )
        if cur.fetchone():
            flash("Purchase failed: customer already has a ticket for this flight and class.", "error")
            return back_to_search()

        # 5) check seats sold
        cur.execute(
            """
            SELECT COUNT(*) AS sold
            FROM ticket AS t
            JOIN purchases AS p ON t.ticket_id = p.ticket_id
            WHERE t.airline_name  = %s
              AND t.flight_num    = %s
              AND t.seat_class_id = %s
            """,
            (airline_name, flight_num, seat_class_id)
        )
        sold = cur.fetchone()["sold"]
        if sold >= seat_capacity:
            flash("Purchase failed: no seats available in this class.", "error")
            return back_to_search()

        # 6) compute price based on class
        base_price = flight["base_price"]
        if seat_class_int == 1:
            factor = Decimal("1.0")
        elif seat_class_int == 2:
            factor = Decimal("1.5")
        else:
            factor = Decimal("2.0")
        purchase_price = int(Decimal(str(base_price)) * factor)

        # 7) create ticket and purchase (ticket_id not auto-incremented)
        cur.execute("SELECT COALESCE(MAX(ticket_id), 0) + 1 AS next_id FROM ticket")
        next_ticket_id = cur.fetchone()["next_id"]
        cur.execute(
            """
            INSERT INTO ticket (ticket_id, airline_name, flight_num, airplane_id, seat_class_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (next_ticket_id, airline_name, flight_num, airplane_id, seat_class_id)
        )
        cur.execute(
            """
            INSERT INTO purchases
                (ticket_id, customer_email, booking_agent_email, purchase_date, purchase_price)
            VALUES
                (%s, %s, %s, CURDATE(), %s)
            """,
            (next_ticket_id, customer_email, agent_email, purchase_price)
        )

        conn.commit()
        flash(f"Ticket successfully purchased for {customer_email}. Price: {purchase_price}", "success")
        return back_to_search()

    except Exception as e:
        conn.rollback()
        print("Agent purchase ERROR:", e)
        flash("Purchase failed due to a system error. Please try again.", "error")
        return back_to_search()

    finally:
        cur.close()
        conn.close()


@agent_bp.route('/analytics')
@agent_login_required
def analytics():
    agent_email = session.get('user_email')
    
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # 1) Commission totals, avg commission, tickets sold (last 30 days)
        cur.execute(
            """
            SELECT 
                IFNULL(SUM(purchase_price) * 0.10, 0) AS total_commission,
                COUNT(*) AS tickets_sold,
                CASE 
                    WHEN COUNT(*) > 0 
                    THEN (SUM(purchase_price) * 0.10) / COUNT(*) 
                    ELSE 0 
                END AS avg_commission
            FROM purchases
            WHERE booking_agent_email = %s
              AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            """,
            (agent_email,)
        )
        stats_30 = cur.fetchone()

        # 2) Top 5 customers by number of tickets (last 6 months)
        cur.execute(
            """
            SELECT 
                customer_email,
                COUNT(*) AS tickets_count
            FROM purchases
            WHERE booking_agent_email = %s
              AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY customer_email
            ORDER BY tickets_count DESC
            LIMIT 5
            """,
            (agent_email,)
        )
        top_customers_6_months = cur.fetchall()

        # 3) Top 5 customers by total commission (last year)
        cur.execute(
            """
            SELECT 
                customer_email,
                SUM(purchase_price) * 0.10 AS total_commission
            FROM purchases
            WHERE booking_agent_email = %s
              AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
            GROUP BY customer_email
            ORDER BY total_commission DESC
            LIMIT 5
            """,
            (agent_email,)
        )
        top_customers_1_year = cur.fetchall()

        return render_template(
            "agent.analytics.html",
            stats_30=stats_30,
            top_customers_6_months=top_customers_6_months,
            top_customers_1_year=top_customers_1_year
        )

    except Exception as e:
        print("AGENT ANALYTICS ERROR:", e)
        flash("Failed to load analytics. Please try again.", "error")
        return redirect(url_for('agent.dashboard'))

    finally:
        cur.close()
        conn.close()
