import socket
import socks
import pymysql
import time
from stem import Signal
from stem.control import Controller

# --- CONFIGURATION ---
# 1. Connect to the LOCAL Tor proxy on this Mac (not the Windows one)
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9050

# 2. The Onion Address from your Windows 'hostname' file
ONION_LINK = '4wfv3o2lpxgz456iv7jubx65frp6ivbzbro2vbxflzmasldjryxv76ad.onion'

DB_USER = "root"  # Use the limited user we created earlier!
DB_PASS = "Tamer@2006"
DB_NAME = "p2p_communication"


# --- THE MONKEY PATCH (Must run once globally) ---
def patch_socket_for_tor():
    """
    Forces Python to use Tor for all connections and prevents
    local DNS lookups (which would fail for .onion addresses).
    """
    socks.set_default_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT, rdns=True)
    socket.socket = socks.socksocket

    # Patch getaddrinfo to prevent DNS leaks and handle .onion resolution
    def getaddrinfo(*args):
        # This tricks Python into passing the hostname directly to the proxy
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (args[0], args[1]))]

    socket.getaddrinfo = getaddrinfo
    print(f"🛡️  Tor Mode Enabled. Tunneling via {PROXY_HOST}:{PROXY_PORT}")


# Apply the patch immediately
patch_socket_for_tor()


# --- DATABASE FUNCTIONS ---

def get_connection():
    print(f"🧅 Connecting to {ONION_LINK}...")
    try:
        return pymysql.connect(
            host=ONION_LINK,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=3306,
            connect_timeout=60,  # Tor is slow, give it time
            read_timeout=60,
            write_timeout=60,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    except pymysql.Error as e:
        print(f"❌ Connection Error: {e}")
        return None


def test_connection():
    conn = get_connection()
    if conn:
        print("✅ SUCCESS! Connected to Windows DB via Tor.")
        conn.close()
    else:
        print("⚠️  Failed. Is Tor running on BOTH machines?")


if __name__ == "__main__":
    test_connection()