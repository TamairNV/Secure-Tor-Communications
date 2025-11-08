import os
import subprocess

torrc = f"""
DataDirectory {os.path.abspath("tor/tor_data")}
HiddenServiceDir {os.path.abspath("tor/tor_hidden_service")}
HiddenServicePort 80 127.0.0.1:8000

HiddenServiceDir {os.path.abspath("tor/tor_hidden_service_mysql")}
HiddenServicePort 3306 127.0.0.1:3306            
Log notice stdout
SocksPort 9050
ControlPort 9051
CookieAuthentication 1
"""

with open("torrc", "w") as f:
    f.write(torrc)

import platform

if platform.system() == "Windows":
    subprocess.run([
        './windows-tor/tor.exe',
        '-f', './torrc',
    ])
else:
    subprocess.run([
        './mac-tor/tor/tor',
        '-f', './torrc',
    ])
    path = os.path.abspath("mac-tor/tor")
    modified_path = '/'.join(path.split('/')[3:])
    try:
        output = subprocess.check_output(["lsof", "-i", ":9050"]).decode().strip()
        lines = output.split('\n')
        if len(lines) > 1:  # Skip header line
            pid = lines[1].split()[1]  # 2nd line, 2nd column (PID)
            print("Extracted PID:", pid)
        else:
            print("No process listening on port 9050.")

        os.system(f"kill -9 {pid}")
    except:
        print("No process listening on port 9050.")
    os.system(f"cd {modified_path}")
    os.system(f"tor -f {os.path.abspath('torrc')}")

    print(f"""
    
    if doesn't run.
    run this in terminal:
    cd {modified_path}
    tor -f {os.path.abspath("torrc")}
    
    and maybe this 
    chmod 700 /Users/tamer/Desktop/FlaskUni/Secure-Tor-Communications/tor/tor_hidden_service/
    chmod 700 /Users/tamer/Desktop/FlaskUni/Secure-Tor-Communications/tor/tor_hidden_service_mysql/
    """)
