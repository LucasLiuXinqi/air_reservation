from flask import Blueprint, flash, request, render_template, redirect, url_for, session
from db import get_connection

search_flights_bp = Blueprint("search_flights", __name__, url_prefix="/search_flights")


@search_flights_bp.route("/", methods=["GET"])
def search_flights():
    # read inputs
    origin = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()
    date = request.args.get("date", "").strip()
    
    # validation
    if date == "":
        flash("Please select a date")
        return redirect(url_for("customer.index"))

    if origin == "" and destination == "":
        flash("Please enter origin or destination")
        return redirect(url_for("customer.index"))
    
    # build query
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    
    # SQL query
    sql = """
        SELECT
            f.airline_name,
            f.flight_num,
            f.departure_airport,
            f.arrival_airport,
            f.departure_time,
            f.arrival_time,
            f.airplane_id,
            f.base_price,
            a1.airport_city AS origin_city,
            a1.airport_name AS origin_airport_name,
            a2.airport_city AS dest_city,
            a2.airport_name AS dest_airport_name
        FROM Flight AS f
        JOIN Airport AS a1 ON f.departure_airport = a1.airport_name
        JOIN Airport AS a2 ON f.arrival_airport   = a2.airport_name
    """
    params = []
    
    if session.get("user_role") == "agent":
        # if agent, limit airlines
        sql += """
            JOIN agent_airline_authorization AS auth
                ON auth.airline_name = f.airline_name
            WHERE auth.agent_email = %s
                AND DATE(f.departure_time) = %s
        """
        params.extend([session["user_email"], date])

    else:
        # customer or public user
        sql += """
            WHERE DATE(f.departure_time) = %s
        """
        params.append(date)
    
    if origin != "":
        sql += " AND (a1.airport_city LIKE %s OR a1.airport_name LIKE %s)"
        like_origin = f"%{origin}%"
        params.extend([like_origin, like_origin])
        
    if destination != "":
        sql += " AND (a2.airport_city LIKE %s OR a2.airport_name LIKE %s)"
        like_destination = f"%{destination}%"
        params.extend([like_destination, like_destination])
        
    sql += " ORDER BY f.departure_time ASC;"
    
    # execute query
    cur.execute(sql, tuple(params))
    flights = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template(
        "search_flights.html",
        flights=flights,
        origin=origin,
        destination=destination,
        date=date,
    )
