# file: hotspot.py

import subprocess
import time

def start_hotspot(ssid, password, site_ip, interface):
    """Sets up a WiFi hotspot with the given configuration."""
    subprocess.run("pkill -f dnsmasq", shell=True)
    time.sleep(1)
    subprocess.run(f"ip addr flush dev {interface}", shell=True)

    with open("hostapd.conf", "w") as f:
        f.write(f"""
interface={interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
""")

    with open("dnsmasq.conf", "w") as f:
        f.write(f"""
interface={interface}
dhcp-range=192.168.4.10,192.168.4.100,12h
""")

    subprocess.run(f"ip link set {interface} down", shell=True)
    subprocess.run(f"iw dev {interface} set type __ap", shell=True)
    subprocess.run(f"ip link set {interface} up", shell=True)
    subprocess.run(f"ip addr add {site_ip}/24 dev {interface}", shell=True)
    subprocess.run("sysctl -w net.ipv4.ip_forward=1", shell=True)
    subprocess.run("iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE", shell=True)
    subprocess.run(f"iptables -A FORWARD -i {interface} -o eth0 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -A FORWARD -i eth0 -o {interface} -m state --state RELATED,ESTABLISHED -j ACCEPT", shell=True)

    print("Launching dnsmasq...")
    result = subprocess.run("dnsmasq -C dnsmasq.conf", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("DNSMASQ OUT:", result.stdout.decode())
    print("DNSMASQ ERR:", result.stderr.decode())

    subprocess.Popen("hostapd hostapd.conf", shell=True)
    time.sleep(3)
