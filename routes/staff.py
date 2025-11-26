from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps
from db import get_connection

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


def staff_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("user_role") != "staff":
            flash("Please log in as airline staff.")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


@staff_bp.route("/dashboard")
@staff_login_required
def dashboard():
    username = session.get("user_id")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # find airline name for this staff
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

    # default: count upcoming flights in next 30 days
    sql_count = """
        SELECT COUNT(*) AS upcoming_count
        FROM flight
        WHERE airline_name = %s
          AND departure_time >= NOW()
          AND departure_time <= DATE_ADD(NOW(), INTERVAL 30 DAY);
    """
    cur.execute(sql_count, (airline_name,))
    upcoming_count = cur.fetchone()["upcoming_count"]

    # List some upcoming flights
    sql_flights = """
        SELECT flight_num, departure_airport, arrival_airport,
               departure_time, arrival_time, status
        FROM flight
        WHERE airline_name = %s
          AND departure_time >= NOW()
        ORDER BY departure_time
        LIMIT 20;
    """
    cur.execute(sql_flights, (airline_name,))
    flights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "staff_dashboard.html",
        airline_name=airline_name,
        upcoming_count=upcoming_count,
        flights=flights,
    )