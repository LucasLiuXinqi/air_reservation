## Top-level

- `app.py`  
  Main Flask application entry point. Creates the Flask app, loads configuration, registers all blueprints
  (`auth`, `customer`, `agent`, `staff`, `search_flights`, `flight_status`), and defines the root route
  for the public index page.

- `db.py`  
  Wrapper around `mysql.connector`. Exposes `get_connection()` which creates and returns a database
  connection using settings from `config.py`.

- `config.py`  
  Stores configuration values such as MySQL credentials, database name, and Flask secret key.

- `air_reservation.sql`  
  SQL script to create and populate the database schema (tables, foreign keys, and sample data).

- `requirement.txt`  
  Python dependency list (Flask, mysql-connector-python, bcrypt, etc.), used to recreate the environment.

- `.DS_Store` / `.venv` / `venv/` / `__pycache__/`  
  Environment / cache / OS-generated files (not logically part of the application, can be ignored by graders).

## Package: `routes/`

- `routes/__init__.py`  
  Makes `routes` a Python package so blueprints can be imported.

- `routes/auth.py`  
  Authentication and registration logic:
  - Customer and booking-agent registration.
  - Unified login for customers, booking agents, and airline staff (admin/operator) using bcrypt-hashed passwords.
  - Sets session fields (`user_role`, `user_email` or `user_id`, names) and handles logout.

- `routes/customer.py`  
  Customer-facing functionality:
  - Customer dashboard after login.
  - Viewing upcoming and past purchased flights, with date/origin/destination filters.
  - Purchasing tickets for a selected flight.
  - Spending summary (default last 12 months + custom date range).
  - Viewing and editing customer personal information (profile).

- `routes/agent.py`  
  Booking-agent functionality:
  - Agent dashboard after login.
  - Searching flights on behalf of customers (re-uses search logic).
  - Purchasing tickets for a customer (with agent recorded in `purchases`).
  - Commission summary (last 30 days, last year, custom date range).
  - Top customers by tickets and by commission.

- `routes/staff.py`  
  Airline staff functionality and analytics:
  - Decorators `staff_login_required`, `admin_required`, `operator_required`.
  - Staff dashboard listing flights of the staff’s airline with filters (date range, origin, destination).
  - Passenger list for a particular flight.
  - All flights taken by a specific customer on the staff airline.
  - Analytics: top booking agents, most frequent customer, tickets sold per month, delay vs on-time stats, top destinations.
  - Admin actions: add airports and airplanes, create new flights, associate booking agents with the airline.
  - Operator actions: update status of flights (e.g., on-time, delayed, in-progress).

- `routes/search_flights.py`  
  Public flight-search logic:
  - Handles search requests from the home page.
  - Accepts origin, destination, and date (date required; origin/destination optional).
  - Returns matching upcoming flights for display in `search_results.html`.

- `routes/flight_status.py`  
  Public flight-status lookup:
  - Takes airline name and flight number from the home page form.
  - Queries the `flight` table and renders `flight_status.html`.

## Templates: `templates/`

- `templates/base.html`  
  Base layout. Defines the common HTML structure, navigation bar (Home / Login / Register plus role-specific tabs),
  flash message area, and `{% block content %}` for child templates.

- `templates/index.html`  
  Public home page extending `base.html`. Contains:
  - “Search Upcoming Flights” form.
  - “Check Flight Status” form.

- `templates/login.html`  
  Login form (email/username + password). On success, redirects to customer / agent / staff dashboards depending on role.

- `templates/register.html`  
  Registration form for new customers and booking agents.

- `templates/customer_dashboard.html`  
  Customer home after login. Shows upcoming flights and navigation links to search, spending, and profile.

- `templates/customer_flights.html`  
  Displays all flights purchased by the logged-in customer with filters (date range, origin, destination).

- `templates/customer_spending.html`  
  Spending summary page. Shows total spending over a chosen interval and a table / bar-chart-friendly list of
  monthly spending (default last 6–12 months, plus custom date range).

- `templates/customer_profile.html`  
  View and edit customer profile (name, address, phone, passport information, etc.).

- `templates/search_results.html`  
  Shows a list of flights that match the search criteria. For logged-in users, includes purchase controls (seat class etc.).

- `templates/flight_status.html`  
  Displays status for a specific flight (airline, flight number, status). Shows a message if no matching flight is found.

- `templates/agent_dashboard.html`  
  Booking agent home. Includes:
  - flight search form for customers,
  - quick stats about recent tickets / commissions,
  - links to commission and top-customer pages.

- `templates/agent_commission.html`  
  Shows agent commissions:
  - total commission and average commission per ticket for last 30 days and last year,
  - custom date-range commission summary.

- `templates/agent_customers.html`  
  Lists the agent’s top customers by number of tickets and by total commission.

- `templates/staff_dashboard.html`  
  Staff view of flights for their airline with filter controls (date_from, date_to, origin, destination).

- `templates/staff_passengers.html`  
  Passenger list for a specific flight, showing customer details, seat class, and purchase data.

- `templates/staff_customer_flights.html`  
  Shows all flights taken by a given customer on the staff’s airline, with optional date filters.

- `templates/staff_analytics.html`  
  Staff analytics page: top booking agents by month/year, most frequent customer, tickets sold per month,
  delay vs on-time counts, and top destinations for last 3 months and last year.

- `templates/staff_admin_home.html`  
  Admin-only page with forms for:
  - adding new airports,
  - adding new airplanes,
  - creating new flights,
  - associating booking agents with the staff’s airline.

- `templates/staff_operator_home.html`  
  Operator-only page with tools to update the status of flights (e.g., mark delayed / on-time / in-progress).

- `templates/error.html` (if present)  
  Generic error-page template used for unexpected failures.

## Static assets: `static/`

- `static/main.css`  
  Global CSS styles for the entire site (navbar, tables, forms, flash messages, etc.).

- Any other `.css`, `.js`, or image files placed here are served as static resources.
