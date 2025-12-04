# Air Reservation

Flask + MySQL demo for an airline reservation system. Customers, booking agents, and airline staff each get their own dashboards for searching flights, purchasing tickets, and running analytics. The repo also ships with a sample schema and seed data to get you started quickly.

## Stack
- Python 3 / Flask 3
- MySQL (tested with MariaDB 10.4)
- Jinja2 templates, plain CSS (`static/main.css`)

## Quick start
1) Install Python deps (use a virtualenv if you prefer):
```bash
pip install -r requirement.txt
```
2) Create the database and import the seed data:
```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS air_reservation CHARACTER SET utf8mb4;"
mysql -u root -p air_reservation < air_reservation.sql
```
3) Configure credentials and secrets in `config.py` (`DB_CONFIG` and `SECRET_KEY`).
4) Run the app (uses port 5000 by default):
```bash
python app.py
```
5) Optional sanity check: `python test.py` lists tables to confirm the DB connection.

## Roles and features
- Public: search flights by date/origin/destination and look up flight status.
- Customer: register/login, search and purchase seats by class with capacity checks, view upcoming/all trips, spending analytics (12 months + custom range), and edit profile details.
- Booking agent: purchase on behalf of customers (enforces seat capacity and prevents duplicates), filter purchased tickets, and view commission/top-customer analytics.
- Airline staff:
  - Dashboard filtered to their airline with date/origin/destination filters.
  - Passenger list per flight and customer-flight lookup.
  - Analytics: top agents (month/year), frequent customer, tickets per month, delay stats, and top destination cities.
  - Admin: add airports/airplanes/seat-class capacities, authorize agents, create flights.
  - Operator: update flight statuses with validation.

## Seed logins (from `air_reservation.sql`)
- Customers with plaintext passwords: `david@example.com / davidpass`, `emma@example.com / emmapass`.
- Booking agent with plaintext password: `agent_premium@agency.com / agentpass3`.
- Staff with plaintext passwords: `delta_admin / staffpass1` (admin), `delta_ops / staffpass2` (operator), `cea_ops / staffpass5` (operator), `united_both / staffpass3` (role “both”).
- Other seeded accounts use bcrypt hashes; reset their passwords in the DB if needed.

## Project layout
- `app.py` – Flask app factory and blueprint registration.
- `routes/` – Blueprints for auth, customer, agent, staff, flight search/status.
- `templates/` and `static/` – Jinja templates and styles.
- `db.py`, `config.py` – MySQL connection helper and configuration.
- `air_reservation.sql` – Schema + sample data for flights, tickets, users, and analytics scenarios.

## Notes
- Default port is 5000 (set intentionally to avoid macOS AirPlay conflicts on 5000/airplayd). Adjust in `app.py` if needed.
- Ticket IDs are manually assigned in code because the `ticket` table is not auto-incremented; keep that in mind if you alter the schema.
