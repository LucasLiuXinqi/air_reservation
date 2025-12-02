from flask import Flask
from config import SECRET_KEY
from routes.auth import auth_bp
from routes.customer import customer_bp
from routes.agent import agent_bp
from routes.staff import staff_bp
from routes.search_flights import search_flights_bp
from routes.flight_status import flight_status_bp

app = Flask(__name__)
app.secret_key = SECRET_KEY

# register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(agent_bp)
app.register_blueprint(staff_bp)
app.register_blueprint(search_flights_bp)
app.register_blueprint(flight_status_bp)


@app.template_filter("display_status")
def display_status(value):
    """Map internal status codes to user-friendly labels."""
    return "on-time" if value == "in-progress" else value


if __name__ == "__main__":
    # Use a non-default port to avoid macOS AirPlay Receiver collision on 5000
    app.run(debug=True, port=5000)
