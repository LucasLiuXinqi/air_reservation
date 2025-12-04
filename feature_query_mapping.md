# Feature ↔ Query Mapping
High-level map of user-facing flows to the SQL they execute (table/columns included when helpful).

## Public / Shared
- Search flights (`/search_flights/`): `SELECT ... FROM Flight f JOIN Airport ... [optionally JOIN agent_airline_authorization for agents] WHERE DATE(f.departure_time)=? AND origin/destination LIKE ? ORDER BY f.departure_time`.
- Check flight status (`/flight_status/`): `SELECT status, airline_name, flight_num FROM flight WHERE airline_name=? AND flight_num=? ORDER BY departure_time DESC`.

## Auth
- Customer/agent/staff login: `SELECT * FROM customer|booking_agent|airline_staff WHERE email/username=?`.
- Customer register: `SELECT COUNT(*) FROM Customer WHERE email=?`; `INSERT INTO customer (...) VALUES (...)`.

## Customer
- Dashboard (my trips): `SELECT ... FROM purchases p JOIN ticket t JOIN flight f JOIN airport ... WHERE p.customer_email=? [filters: departure_time range, origin/dest city/airport, upcoming/all] ORDER BY f.departure_time DESC`.
- Purchase ticket: capacity check `SELECT seat_capacity FROM seat_class JOIN flight WHERE flight match`; sold count `SELECT COUNT(*) FROM ticket JOIN purchases WHERE airline_name=? AND flight_num=? AND seat_class_id=?`; price lookup `SELECT base_price, departure_time FROM flight WHERE airline_name=? AND flight_num=?`; ticket id `SELECT COALESCE(MAX(ticket_id),0)+1 FROM ticket`; insert ticket `INSERT INTO ticket (...)`; insert purchase `INSERT INTO purchases (ticket_id, customer_email, booking_agent_email, purchase_date, purchase_price) VALUES (...)`.
- Spending analytics: 12-month total `SELECT IFNULL(SUM(purchase_price),0) FROM purchases WHERE customer_email=? AND purchase_date>=DATE_SUB(CURDATE(), INTERVAL 12 MONTH)`; last 6 months by month `SELECT DATE_FORMAT(purchase_date,'%Y-%m'), SUM(purchase_price) FROM purchases WHERE customer_email=? AND purchase_date>=DATE_SUB(CURDATE(), INTERVAL 6 MONTH) GROUP BY ym ORDER BY ym`; custom range total/by-month similar with `BETWEEN ? AND ?`.
- Profile view/update: `SELECT * FROM customer WHERE email=?`; update `UPDATE customer SET ... WHERE email=?`.

## Booking Agent
- Dashboard (purchased tickets): `SELECT ... FROM purchases p JOIN ticket t JOIN flight f JOIN airport ... WHERE p.booking_agent_email=? [filters: purchase_date range, origin/dest] ORDER BY p.purchase_date DESC`.
- Purchase for customer: exists check `SELECT 1 FROM customer WHERE email=?`; flight exists/time `SELECT base_price, departure_time FROM flight WHERE airline_name=? AND flight_num=? AND airplane_id=?`; seat capacity `SELECT seat_capacity FROM seat_class JOIN flight WHERE match`; duplicate check `SELECT 1 FROM ticket JOIN purchases WHERE airline_name=? AND flight_num=? AND seat_class_id=? AND customer_email=? LIMIT 1`; sold count same as customer; next ticket id `SELECT COALESCE(MAX(ticket_id),0)+1 FROM ticket`; insert ticket `INSERT INTO ticket (...)`; insert purchase `INSERT INTO purchases (ticket_id, customer_email, booking_agent_email, purchase_date, purchase_price) VALUES (...)`.
- Agent analytics: 30-day commission `SELECT IFNULL(SUM(purchase_price)*0.10,0) AS total_commission, COUNT(*) AS tickets_sold, CASE WHEN COUNT(*)>0 THEN (SUM(purchase_price)*0.10)/COUNT(*) ELSE 0 END AS avg_commission FROM purchases WHERE booking_agent_email=? AND purchase_date>=DATE_SUB(CURDATE(), INTERVAL 30 DAY)`; top 5 customers by tickets (6 months) `SELECT customer_email, COUNT(*) FROM purchases WHERE booking_agent_email=? AND purchase_date>=DATE_SUB(CURDATE(), INTERVAL 6 MONTH) GROUP BY customer_email ORDER BY tickets_count DESC LIMIT 5`; top 5 customers by commission (1 year) similar with `SUM(purchase_price)*0.10`.

## Airline Staff
- Dashboard (flights for airline): fetch airline `SELECT airline_name, first_name, last_name FROM airline_staff WHERE username=?`; list flights `SELECT flight_num, departure_airport, arrival_airport, departure_time, arrival_time, status FROM flight WHERE airline_name=? [filters: departure_time range, origin, destination] ORDER BY departure_time`.
- Passengers per flight: airline lookup as above; passengers query `SELECT c.email, c.name, t.seat_class_id, p.purchase_date, p.purchase_price, f.* FROM purchases p JOIN ticket t ON p.ticket_id=t.ticket_id JOIN customer c ON p.customer_email=c.email JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num WHERE f.airline_name=? AND f.flight_num=? [AND DATE(f.departure_time)=?] ORDER BY c.name, p.purchase_date`.
- Customer flights (for airline): `SELECT f.*, t.seat_class_id, p.purchase_date, p.purchase_price FROM purchases p JOIN ticket t ON p.ticket_id=t.ticket_id JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num WHERE f.airline_name=? AND p.customer_email=? [date filters] ORDER BY p.purchase_date DESC`.
- Analytics:
  - Top booking agents last month/year (tickets + commission): `SELECT booking_agent_email, COUNT(*), SUM(purchase_price)*0.10 FROM purchases p JOIN ticket t ON p.ticket_id=t.ticket_id WHERE p.booking_agent_email IS NOT NULL AND t.airline_name=? AND p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 1 MONTH/1 YEAR) GROUP BY booking_agent_email ORDER BY tickets_sold DESC LIMIT 5`.
  - Most frequent customer (1 year): `SELECT customer_email, COUNT(*) AS flights_taken FROM purchases p JOIN ticket t ON p.ticket_id=t.ticket_id WHERE t.airline_name=? AND p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 1 YEAR) GROUP BY customer_email ORDER BY flights_taken DESC LIMIT 1`.
  - Tickets sold per month (12 months): `SELECT DATE_FORMAT(p.purchase_date,'%Y-%m') AS month, COUNT(*) FROM purchases p JOIN ticket t ON p.ticket_id=t.ticket_id WHERE t.airline_name=? AND p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 12 MONTH) GROUP BY month ORDER BY month ASC`.
  - Delay stats: `SELECT SUM(CASE WHEN f.status='delayed' THEN 1 ELSE 0 END) AS delayed_count, SUM(CASE WHEN f.status='in-progress' THEN 1 ELSE 0 END) AS ontime_count, SUM(CASE WHEN f.status NOT IN ('delayed','on-time') THEN 1 ELSE 0 END) AS other_count FROM flight f WHERE f.airline_name=? AND f.departure_time>=DATE_SUB(CURDATE(), INTERVAL 1 YEAR)`.
  - Top destination cities (3 months / 1 year): `SELECT a.airport_city, COUNT(*) FROM flight f JOIN airport a ON f.arrival_airport=a.airport_name WHERE f.airline_name=? AND f.departure_time>=DATE_SUB(CURDATE(), INTERVAL 3 MONTH / 1 YEAR) GROUP BY a.airport_city ORDER BY flights DESC LIMIT 5`.
- Admin actions:
  - Add airport: `INSERT INTO airport (airport_name, airport_city) VALUES (?,?)`.
  - Add airplane: optional seat capacity column; `INSERT INTO airplane (airplane_id, airline_name [, seat_capacity]) VALUES (...)`; seat classes `INSERT INTO seat_class (airline_name, airplane_id, seat_class_id, seat_capacity) VALUES (...) ON DUPLICATE KEY UPDATE seat_capacity=VALUES(seat_capacity)`.
  - Associate booking agent: `INSERT IGNORE INTO agent_airline_authorization (agent_email, airline_name) VALUES (?,?)`.
  - Create flight: `INSERT INTO flight (airline_name, flight_num, departure_airport, departure_time, arrival_airport, arrival_time, base_price, airplane_id, status) VALUES (...)`.
- Operator actions:
  - Update flight status: `UPDATE flight SET status=? WHERE airline_name=? AND flight_num=?`.
  - List flights (filtered): same query as dashboard but ordered DESC and limited.
