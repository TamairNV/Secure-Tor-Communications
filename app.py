import secrets
import socket
from pathlib import Path
from flask import Flask, session, redirect, url_for
from flask_apscheduler import APScheduler

from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.friend import friend_bp

from utils.tor import get_onion_address


s = socket.socket()
try:
    s.connect(("127.0.0.1", ))
    print("✅ SOCKS proxy is running on port 9050")
except:
    print("❌ Tor SOCKS proxy not available on 9050")
print(f"""
This is your onion address: {get_onion_address()}
""")

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


class Config:
    SCHEDULER_API_ENABLED = True  # Optional: Exposes a REST API for managing jobs


app.config.from_object(Config())

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


def my_background_task():
    print("This task runs every 2 seconds.")




@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))


# @app.teardown_appcontext
# def teardown(exception=None):
#    SQL_manager.execute_query("UPDATE users SET is_online = FALSE WHERE user_id = %s", (session['user_id'],))

if __name__ == '__main__':

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(friend_bp, url_prefix='/friend')

    # Disable the reloader to prevent multiple initializations of global code and APScheduler
    app.run(port=8000, debug=True, use_reloader=False)
