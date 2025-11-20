import socket
import socks
import pymysql
from pymysql.cursors import DictCursor

# --- CONFIGURATION ---
DB_CONFIG = {
    "host":"192.168.1.24",
    "user": "Home_User",
    "password": "Tamer@2006",  # Ideally load this from env variables
    "db_name": "p2p_communication",
    "mode": "local"  # 'local' or 'tor'
}


def configure_connection(target_host):
    """
    Sets the target DB.
    - If target_host contains '.onion', it enables the Tor proxy.
    - If target_host is an IP (e.g., 127.0.0.1), it uses a standard connection.
    """
    DB_CONFIG["host"] = target_host

    if ".onion" in target_host:
        DB_CONFIG["mode"] = "tor"
        enable_tor_proxy()
    else:
        DB_CONFIG["mode"] = "local"
        # Note: Once socks is patched globally, it's hard to un-patch without restart.
        # If switching modes dynamically in one session is required, logic needs to be stricter.
        # For now, we assume the mode is set once at startup.


def enable_tor_proxy():
    PROXY_HOST = "127.0.0.1"
    PROXY_PORT = 9050

    socks.set_default_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT, rdns=True)
    socket.socket = socks.socksocket

    # Patch getaddrinfo to prevent DNS leaks and handle .onion resolution
    def getaddrinfo_patched(*args):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (args[0], args[1]))]

    socket.getaddrinfo = getaddrinfo_patched
    print(f"🛡️ Tor Proxy Enabled. Tunneling to {DB_CONFIG['host']}")


def get_connection():
    """
    Establishes a database connection based on the current configuration.
    Returns a pymysql connection object or None if failed.
    """
    if not DB_CONFIG["host"]:
        # Fallback or explicit error if setup hasn't run
        print("⚠️ DB Host not configured. Run /setup first.")
        return None

    print(f"🔌 Connecting to database at {DB_CONFIG['host']}...")
    try:
        return pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["db_name"],
            port=3306,
            connect_timeout=60,
            read_timeout=60,
            write_timeout=60,
            charset='utf8mb4',
            cursorclass=DictCursor
        )
    except pymysql.Error as e:
        print(f"❌ Connection Error: {e}")
        return None


def execute_query(query, params=None, fetch=False):
    """
    Executes a SQL query safely managing the connection.

    Args:
        query (str): The SQL query to execute.
        params (tuple/list): Parameters to substitute in the query.
        fetch (bool): If True, returns the results of the query.

    Returns:
        dict: {'results': [rows]} if fetch=True, else {'status': 'success'}
    """
    conn = get_connection()
    if not conn:
        print("❌ Cannot execute query: No connection established.")
        return {"results": []}

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)

            if fetch:
                result = cursor.fetchall()
                return {"results": result}
            else:
                conn.commit()
                return {"status": "success"}

    except Exception as e:
        print(f"❌ Query Execution Failed: {e}")
        return {"results": [], "error": str(e)}

    finally:
        if conn:
            conn.close()