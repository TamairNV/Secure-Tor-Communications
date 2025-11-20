import secrets
import socket
import time
from flask import Flask, session, redirect, url_for, render_template, request
from flask_apscheduler import APScheduler

# Import the new tools
from utils.tor_manager import TorManager
import utils.SQL_manager as sql_manager
from utils.tor import get_onion_address  # Optional, if you still use this for the web part

# Initialize Managers
tor_man = TorManager()
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Global State
APP_STATE = {
    "setup_complete": False,
    "role": None,  # 'server' or 'client'
    "db_host": None
}


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        role = request.form.get('role')

        if role == 'host':
            # 1. Start Tor as Server (Hidden Service)
            tor_man.start_tor(mode='server')

            # 2. Get the Onion Link to share
            onion_link = tor_man.get_db_onion()

            # 3. Configure DB to use Localhost (since we ARE the server)
            # Using 127.0.0.1 avoids routing our own DB traffic through Tor
            APP_STATE['db_host'] = '127.0.0.1'
            sql_manager.configure_connection('127.0.0.1')

            APP_STATE['role'] = 'server'
            APP_STATE['setup_complete'] = True

            # Show the user their special link
            return f"""
            <h1>Server Started!</h1>
            <p>Share this Onion Link with your friends so they can connect:</p>
            <code>{onion_link}</code>
            <br><br>
            <a href="/">Go to Login</a>
            """

        elif role == 'join':
            onion_link = request.form.get('onion_link')

            # 1. Start Tor as Client (Proxy Only)
            tor_man.start_tor(mode='client')

            # 2. Configure DB to use the Onion Link
            APP_STATE['db_host'] = onion_link
            sql_manager.configure_connection(onion_link)

            APP_STATE['role'] = 'client'
            APP_STATE['setup_complete'] = True

            return redirect(url_for('index'))

    # Simple HTML for the setup choice
    return """
    <h1>Secure Chat Setup</h1>
    <form method="POST">
        <h3>I want to:</h3>
        <button name="role" value="host">Host a Chat Group (Server)</button>
        <hr>
        <h3>Or Join a Group:</h3>
        Enter Friend's Onion Link: <input type="text" name="onion_link" placeholder="example.onion">
        <button name="role" value="join">Join</button>
    </form>
    """


@app.route('/')
def index():
    # Redirect to setup if not done
    if not APP_STATE['setup_complete']:
        return redirect(url_for('setup'))

    if 'username' in session:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))


if __name__ == '__main__':
    # Note: We do NOT start Tor here automatically anymore.
    # It starts when the user completes the /setup flow.

    from routes.auth import auth_bp
    from routes.chat import chat_bp
    from routes.friend import friend_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(friend_bp, url_prefix='/friend')

    app.run(port=8001, debug=True, use_reloader=False)