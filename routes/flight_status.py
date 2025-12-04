from db import get_connection
from flask import Blueprint, render_template, request, flash, redirect, url_for, session

flight_status_bp = Blueprint("flight_status", __name__, url_prefix="/flight_status")


@flight_status_bp.route("/")
def flight_status():
    # read inputs
    airline = request.args.get("airline", "").strip()
    flight_num = request.args.get("flight_num", "").strip()
    
    # validation
    if airline == "" or flight_num == "":
        flash("Please provide both airline and flight number.")
        return redirect(url_for("customer.index"))
    
    # build query
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Agents can only query airlines they are authorized to sell
    if session.get("user_role") == "agent":
        cur.execute(
            """
            SELECT 1
            FROM agent_airline_authorization
            WHERE agent_email = %s AND airline_name = %s
            LIMIT 1;
            """,
            (session.get("user_email"), airline),
        )
        if cur.fetchone() is None:
            cur.close()
            conn.close()
            flash("You are not authorized to view flights for this airline.")
            return redirect(url_for("customer.index"))
    
    # SQL query
    sql = """
        SELECT status, airline_name, flight_num
        FROM flight
        WHERE airline_name = %s AND flight_num = %s
        ORDER BY departure_time DESC;
        """
        
    params = (airline, flight_num)
    
    # execute query
    cur.execute(sql, params)
    result = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template(
        "flight_status.html",
        result=result
    )

    
