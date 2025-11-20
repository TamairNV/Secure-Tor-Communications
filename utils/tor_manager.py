import os
import subprocess
import platform
import time
import sys


class TorManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.tor_data_dir = os.path.join(self.base_dir, "tor", "tor_data")
        self.hs_dir_db = os.path.join(self.base_dir, "tor", "tor_hidden_service_mysql")
        self.torrc_path = os.path.join(self.base_dir, "torrc")
        self.tor_pid = None

        # Define binary paths
        if platform.system() == "Windows":
            self.tor_bin = os.path.join(self.base_dir, "windows-tor", "tor.exe")
        else:
            self.tor_bin = os.path.join(self.base_dir, "mac-tor", "tor", "tor")

    def _ensure_permissions(self):
        """Fixes permissions for Tor directories on Mac/Linux"""
        if platform.system() != "Windows":
            try:
                for path in [self.tor_data_dir, self.hs_dir_db]:
                    if not os.path.exists(path):
                        os.makedirs(path)
                    os.chmod(path, 0o700)
            except Exception as e:
                print(f"⚠️ Permission warning: {e}")

    def start_tor(self, mode='client', redirect_ip='127.0.0.1'):
        """
        mode='server': Enables Hidden Service for MySQL.
        mode='client': Starts Tor as a SOCKS proxy only.
        redirect_ip: Where the Hidden Service should forward traffic (default 127.0.0.1)
        """
        self._ensure_permissions()

        # 1. Create Dynamic Torrc
        config_lines = [
            f"DataDirectory {self.tor_data_dir}",
            "SocksPort 9050",
            "Log notice stdout",
            "CookieAuthentication 1"
        ]

        if mode == 'server':
            print(f"🛠️ Configuring as SERVER (Forwarding to {redirect_ip}:3306)...")
            config_lines.append(f"HiddenServiceDir {self.hs_dir_db}")
            # FIX: Use the specific redirect_ip instead of hardcoding 127.0.0.1
            config_lines.append(f"HiddenServicePort 3306 {redirect_ip}:3306")
        else:
            print("🛠️ Configuring as CLIENT (Connect Only)...")

        with open(self.torrc_path, "w") as f:
            f.write("\n".join(config_lines))

        # 2. Kill existing Tor
        self.stop_tor()

        # 3. Start Tor
        print(f"🚀 Starting Tor in {mode.upper()} mode...")
        if platform.system() == "Windows":
            cmd = [self.tor_bin, '-f', self.torrc_path]
        else:
            cmd = [self.tor_bin, '-f', self.torrc_path]

        self.process = subprocess.Popen(cmd)

        # Wait for boot
        time.sleep(3)
        if mode == 'server':
            print(f"🧅 Database Onion Address: {self.get_db_onion()}")
    def stop_tor(self):
        if platform.system() == "Windows":
            os.system("taskkill /F /IM tor.exe >nul 2>&1")
        else:
            os.system("pkill -x tor")

    def get_db_onion(self):
        hostname_file = os.path.join(self.hs_dir_db, "hostname")
        if os.path.exists(hostname_file):
            with open(hostname_file, 'r') as f:
                return f.read().strip()
        return None