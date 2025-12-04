# Feature ↔ Query Mapping
High-level map of user-facing flows to the SQL they execute (table/columns included when helpful).

## Public / Shared
- Search flights (`/search_flights/`):
  ```sql
  SELECT f.airline_name, f.flight_num, f.departure_airport, f.arrival_airport,
         f.departure_time, f.arrival_time, f.airplane_id, f.base_price,
         a1.airport_city AS origin_city, a1.airport_name AS origin_airport_name,
         a2.airport_city AS dest_city,   a2.airport_name AS dest_airport_name
  FROM Flight AS f
  JOIN Airport AS a1 ON f.departure_airport = a1.airport_name
  JOIN Airport AS a2 ON f.arrival_airport   = a2.airport_name
  [JOIN agent_airline_authorization auth ON auth.airline_name = f.airline_name
   WHERE auth.agent_email = ? AND]
  WHERE DATE(f.departure_time) = ?
    AND origin/destination LIKE ?
  ORDER BY f.departure_time;
  ```
- Check flight status (`/flight_status/`):
  ```sql
  SELECT status, airline_name, flight_num
  FROM flight
  WHERE airline_name = ? AND flight_num = ?
  ORDER BY departure_time DESC;
  ```

## Auth
- Customer/agent/staff login:
  ```sql
  SELECT * FROM customer|booking_agent|airline_staff WHERE email/username = ?;
  ```
- Customer register:
  ```sql
  SELECT COUNT(*) FROM Customer WHERE email = ?;
  INSERT INTO customer (...) VALUES (...);
  ```

## Customer
- Dashboard (my trips):
  ```sql
  SELECT f.airline_name, f.flight_num, f.departure_airport, f.arrival_airport,
         f.departure_time, f.arrival_time, f.status,
         a_dep.airport_city AS origin_city, a_arr.airport_city AS dest_city
  FROM purchases p
  JOIN ticket t ON p.ticket_id = t.ticket_id
  JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
  JOIN airport a_dep ON f.departure_airport = a_dep.airport_name
  JOIN airport a_arr ON f.arrival_airport   = a_arr.airport_name
  WHERE p.customer_email = ?
    [AND f.departure_time >= NOW()]
    [AND DATE(f.departure_time) BETWEEN ? AND ?]
    [AND origin/dest matches]
  ORDER BY f.departure_time DESC;
  ```
- Purchase ticket:
  ```sql
  -- seat capacity
  SELECT sc.seat_capacity
  FROM seat_class sc
  JOIN flight f ON sc.airline_name = f.airline_name AND sc.airplane_id = f.airplane_id
  WHERE f.airline_name = ? AND f.flight_num = ? AND sc.seat_class_id = ?;

  -- sold count
  SELECT COUNT(*) AS sold
  FROM ticket t
  JOIN purchases p ON t.ticket_id = p.ticket_id
  WHERE t.airline_name = ? AND t.flight_num = ? AND t.seat_class_id = ?;

  -- price and time
  SELECT base_price, departure_time FROM flight WHERE airline_name = ? AND flight_num = ?;

  -- next ticket id
  SELECT COALESCE(MAX(ticket_id), 0) + 1 AS next_id FROM ticket;

  -- inserts
  INSERT INTO ticket (ticket_id, airline_name, flight_num, airplane_id, seat_class_id)
  VALUES (...);
  INSERT INTO purchases (ticket_id, customer_email, booking_agent_email, purchase_date, purchase_price)
  VALUES (...);
  ```
- Spending analytics:
  ```sql
  SELECT IFNULL(SUM(purchase_price), 0) AS total_12
  FROM purchases
  WHERE customer_email = ? AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH);

  SELECT DATE_FORMAT(purchase_date, '%Y-%m') AS ym, SUM(purchase_price) AS total
  FROM purchases
  WHERE customer_email = ? AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
  GROUP BY ym ORDER BY ym;

  -- custom range totals and by-month use BETWEEN ? AND ? on purchase_date
  ```
- Profile view/update:
  ```sql
  SELECT * FROM customer WHERE email = ?;
  UPDATE customer SET ... WHERE email = ?;
  ```

## Booking Agent
- Dashboard (purchased tickets):
  ```sql
  SELECT f.airline_name, f.flight_num, f.departure_airport, f.arrival_airport,
         f.departure_time, f.arrival_time, f.status,
         p.customer_email, p.purchase_date, p.purchase_price,
         a_dep.airport_city AS origin_city, a_arr.airport_city AS dest_city
  FROM purchases p
  JOIN ticket t ON p.ticket_id = t.ticket_id
  JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
  JOIN airport a_dep ON f.departure_airport = a_dep.airport_name
  JOIN airport a_arr ON f.arrival_airport   = a_arr.airport_name
  WHERE p.booking_agent_email = ?
    [date/origin/dest filters]
  ORDER BY p.purchase_date DESC;
  ```
- Purchase for customer (similar to customer purchase with agent email):
  ```sql
  SELECT 1 FROM customer WHERE email = ?;
  SELECT base_price, departure_time FROM flight WHERE airline_name = ? AND flight_num = ? AND airplane_id = ?;
  SELECT sc.seat_capacity FROM seat_class sc JOIN flight f ... WHERE ...;
  SELECT 1 FROM ticket t JOIN purchases p ON t.ticket_id = p.ticket_id
   WHERE t.airline_name = ? AND t.flight_num = ? AND t.seat_class_id = ? AND p.customer_email = ? LIMIT 1;
  SELECT COUNT(*) AS sold FROM ticket t JOIN purchases p ON t.ticket_id = p.ticket_id WHERE ...;
  SELECT COALESCE(MAX(ticket_id), 0) + 1 AS next_id FROM ticket;
  INSERT INTO ticket (...); INSERT INTO purchases (...);
  ```
- Agent analytics:
  ```sql
  -- 30-day commission and averages
  SELECT IFNULL(SUM(purchase_price) * 0.10, 0) AS total_commission,
         COUNT(*) AS tickets_sold,
         CASE WHEN COUNT(*) > 0 THEN (SUM(purchase_price) * 0.10) / COUNT(*) ELSE 0 END AS avg_commission
  FROM purchases
  WHERE booking_agent_email = ?
    AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);

  -- top customers by tickets (6 months)
  SELECT customer_email, COUNT(*) AS tickets_count
  FROM purchases
  WHERE booking_agent_email = ?
    AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
  GROUP BY customer_email
  ORDER BY tickets_count DESC
  LIMIT 5;

  -- top customers by commission (1 year)
  SELECT customer_email, SUM(purchase_price) * 0.10 AS total_commission
  FROM purchases
  WHERE booking_agent_email = ?
    AND purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
  GROUP BY customer_email
  ORDER BY total_commission DESC
  LIMIT 5;
  ```

## Airline Staff
- Dashboard (flights for airline):
  ```sql
  SELECT airline_name, first_name, last_name FROM airline_staff WHERE username = ?;

  SELECT flight_num, departure_airport, arrival_airport, departure_time, arrival_time, status
  FROM flight
  WHERE airline_name = ?
    [departure_time range, origin, destination filters]
  ORDER BY departure_time;
  ```
- Passengers per flight:
  ```sql
  SELECT c.email AS customer_email, c.name AS customer_name, t.seat_class_id,
         p.purchase_date, p.purchase_price,
         f.flight_num, f.departure_airport, f.arrival_airport,
         f.departure_time, f.arrival_time
  FROM purchases p
  JOIN ticket t ON p.ticket_id = t.ticket_id
  JOIN customer c ON p.customer_email = c.email
  JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
  WHERE f.airline_name = ?
    AND f.flight_num = ?
    [AND DATE(f.departure_time) = ?]
  ORDER BY c.name, p.purchase_date;
  ```
- Customer flights (for airline):
  ```sql
  SELECT f.airline_name, f.flight_num, f.departure_airport, f.arrival_airport,
         f.departure_time, f.arrival_time, f.status,
         t.seat_class_id, p.purchase_date, p.purchase_price
  FROM purchases p
  JOIN ticket t ON p.ticket_id = t.ticket_id
  JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
  WHERE f.airline_name = ?
    AND p.customer_email = ?
    [date filters]
  ORDER BY p.purchase_date DESC;
  ```
- Analytics:
  ```sql
  -- top agents (month/year)
  SELECT p.booking_agent_email AS agent,
         COUNT(*) AS tickets_sold,
         SUM(purchase_price) * 0.10 AS commission
  FROM purchases p
  JOIN ticket t ON p.ticket_id = t.ticket_id
  WHERE p.booking_agent_email IS NOT NULL
    AND t.airline_name = ?
    AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
  GROUP BY agent
  ORDER BY tickets_sold DESC
  LIMIT 5;
  -- (Repeat with INTERVAL 1 YEAR)

  -- most frequent customer (year)
  SELECT p.customer_email AS customer, COUNT(*) AS flights_taken
  FROM purchases p
  JOIN ticket t ON p.ticket_id = t.ticket_id
  WHERE t.airline_name = ?
    AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
  GROUP BY customer
  ORDER BY flights_taken DESC
  LIMIT 1;

  -- tickets per month (12 months)
  SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') AS month, COUNT(*) AS tickets_sold
  FROM purchases p
  JOIN ticket t ON p.ticket_id = t.ticket_id
  WHERE t.airline_name = ?
    AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
  GROUP BY month
  ORDER BY month ASC;

  -- delay stats
  SELECT SUM(CASE WHEN f.status = 'delayed' THEN 1 ELSE 0 END) AS delayed_count,
         SUM(CASE WHEN f.status = 'in-progress' THEN 1 ELSE 0 END) AS ontime_count,
         SUM(CASE WHEN f.status NOT IN ('delayed','on-time') THEN 1 ELSE 0 END) AS other_count
  FROM flight f
  WHERE f.airline_name = ?
    AND f.departure_time >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR);

  -- top destination cities (3 months / 1 year)
  SELECT a.airport_city AS city, COUNT(*) AS flights
  FROM flight f
  JOIN airport a ON f.arrival_airport = a.airport_name
  WHERE f.airline_name = ?
    AND f.departure_time >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
  GROUP BY city
  ORDER BY flights DESC
  LIMIT 5;
  -- (Repeat with INTERVAL 1 YEAR)
  ```
- Admin actions:
  ```sql
  INSERT INTO airport (airport_name, airport_city) VALUES (?, ?);

  INSERT INTO airplane (airplane_id, airline_name [, seat_capacity]) VALUES (...);
  INSERT INTO seat_class (airline_name, airplane_id, seat_class_id, seat_capacity)
  VALUES (...) ON DUPLICATE KEY UPDATE seat_capacity = VALUES(seat_capacity);

  INSERT IGNORE INTO agent_airline_authorization (agent_email, airline_name)
  VALUES (?, ?);

  INSERT INTO flight (airline_name, flight_num, departure_airport, departure_time,
                      arrival_airport, arrival_time, base_price, airplane_id, status)
  VALUES (...);
  ```
- Operator actions:
  ```sql
  UPDATE flight
  SET status = ?
  WHERE airline_name = ? AND flight_num = ?;

  -- listing flights uses the dashboard query with ORDER BY departure_time DESC LIMIT 200
  ```
