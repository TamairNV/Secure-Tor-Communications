import os
import subprocess
import platform
import time
import sys

# 1. Get the absolute path to the folder where THIS script lives
#    This ensures it works even if you run it from a different directory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define paths relative to this script
TOR_BIN_WINDOWS = os.path.join(BASE_DIR, "windows-tor", "tor.exe")
TOR_BIN_MAC = os.path.join(BASE_DIR, "mac-tor", "tor", "tor")
TOR_DATA_DIR = os.path.join(BASE_DIR, "tor", "tor_data")
HS_DIR_WEB = os.path.join(BASE_DIR, "tor", "tor_hidden_service")
HS_DIR_DB = os.path.join(BASE_DIR, "tor", "tor_hidden_service_mysql")
TORRC_PATH = os.path.join(BASE_DIR, "torrc")


# 2. Ensure Directories Exist & Fix Permissions (Crucial for Mac/Linux)
def ensure_secure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

    # On Mac/Linux, Tor refuses to start if the folder is not chmod 700
    if platform.system() != "Windows":
        try:
            os.chmod(path, 0o700)
            print(f"🔒 Secured directory: {path}")
        except Exception as e:
            print(f"⚠️ Could not set permissions on {path}: {e}")


ensure_secure_dir(TOR_DATA_DIR)
ensure_secure_dir(HS_DIR_WEB)
ensure_secure_dir(HS_DIR_DB)

# 3. Generate torrc with proper paths
torrc_content = f"""
DataDirectory {TOR_DATA_DIR}

# Web Server Hidden Service
HiddenServiceDir {HS_DIR_WEB}
HiddenServicePort 80 127.0.0.1:8000

# MySQL Database Hidden Service
HiddenServiceDir {HS_DIR_DB}
HiddenServicePort 3306 127.0.0.1:3306            

Log notice stdout
SocksPort 9050
ControlPort 9051
CookieAuthentication 1
"""

with open(TORRC_PATH, "w") as f:
    f.write(torrc_content)


# 4. Kill any existing Tor process on port 9050 (Cleanup)
def kill_existing_tor():
    if platform.system() == "Windows":
        os.system("taskkill /F /IM tor.exe >nul 2>&1")
    else:
        # Safer way to find and kill process on port 9050
        try:
            cmd = "lsof -t -i:9050"
            pid = subprocess.check_output(cmd, shell=True).decode().strip()
            if pid:
                print(f"♻️  Killing old Tor process (PID {pid})...")
                os.system(f"kill -9 {pid}")
        except:
            pass  # No process found, that's fine


kill_existing_tor()

# 5. Start Tor Non-Blocking (The Fix)
print("🚀 Starting Tor...")

if platform.system() == "Windows":
    tor_cmd = [TOR_BIN_WINDOWS, '-f', TORRC_PATH]
else:
    tor_cmd = [TOR_BIN_MAC, '-f', TORRC_PATH]

try:
    # Popen allows the script to continue running while Tor runs in background
    tor_process = subprocess.Popen(tor_cmd)
    print(f"✅ Tor started successfully (PID: {tor_process.pid})")

    # Give it a few seconds to generate the keys if this is the first run
    time.sleep(3)


    # Print the Onion Addresses for the user
    def print_onion(name, path):
        hostname_file = os.path.join(path, "hostname")
        if os.path.exists(hostname_file):
            with open(hostname_file, 'r') as f:
                print(f"🔗 {name}: {f.read().strip()}")
        else:
            print(f"⏳ {name}: (Generating keys, please wait...)")


    print_onion("Web Onion", HS_DIR_WEB)
    print_onion("DB Onion ", HS_DIR_DB)

except FileNotFoundError:
    print(f"❌ Error: Could not find Tor executable at: {tor_cmd[0]}")
except Exception as e:
    print(f"❌ Error starting Tor: {e}")