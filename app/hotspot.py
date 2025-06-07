# file: hotspot.py

import subprocess
import time

INTERFACE = "wlan0"
HOTSPOT_IP = "192.168.4.1"
HOTSPOT_SSID = "MyHotspot"
HOTSPOT_PASS = "12345678"

def start_hotspot():
    """Sets up WiFi hotspot with hostapd and dnsmasq."""
    subprocess.run("pkill dnsmasq", shell=True)
    subprocess.run(f"ip addr flush dev {INTERFACE}", shell=True)

    with open("hostapd.conf", "w") as f:
        f.write(f"""
interface={INTERFACE}
driver=nl80211
ssid={HOTSPOT_SSID}
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={HOTSPOT_PASS}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
""")

    with open("dnsmasq.conf", "w") as f:
        f.write(f"""
interface={INTERFACE}
dhcp-range=192.168.4.10,192.168.4.100,12h
""")

    subprocess.run(f"ip link set {INTERFACE} down", shell=True)
    subprocess.run(f"iw dev {INTERFACE} set type __ap", shell=True)
    subprocess.run(f"ip link set {INTERFACE} up", shell=True)
    subprocess.run(f"ip addr add {HOTSPOT_IP}/24 dev {INTERFACE}", shell=True)
    subprocess.run("sysctl -w net.ipv4.ip_forward=1", shell=True)
    subprocess.run("iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE", shell=True)
    subprocess.run(f"iptables -A FORWARD -i {INTERFACE} -o eth0 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -A FORWARD -i eth0 -o {INTERFACE} -m state --state RELATED,ESTABLISHED -j ACCEPT", shell=True)

    subprocess.Popen("dnsmasq -C dnsmasq.conf", shell=True)
    subprocess.Popen("hostapd hostapd.conf", shell=True)
    time.sleep(3)
