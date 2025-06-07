import subprocess
import time
import os
import signal

def start_hotspot(ssid, password, site_ip, interface):
    print("🔥 Starting WiFi Hotspot...")

    # Kill existing dnsmasq/hostapd processes
    kill_process("dnsmasq")
    kill_process("hostapd")

    time.sleep(1)
    run(f"ip addr flush dev {interface}")

    # Write hostapd.conf
    with open("hostapd.conf", "w") as f:
        f.write(f"""interface={interface}
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
    print("📝 hostapd.conf written")

    # Write dnsmasq.conf
    dhcp_base = site_ip.rsplit('.', 1)[0]
    dhcp_range = f"{dhcp_base}.10,{dhcp_base}.100"
    with open("dnsmasq.conf", "w") as f:
        f.write(f"""interface={interface}
dhcp-range={dhcp_range},12h
""")
    print("📝 dnsmasq.conf written")

    # Configure interface
    run(f"ip link set {interface} down")
    run(f"iw dev {interface} set type __ap")
    run(f"ip link set {interface} up")
    run(f"ip addr add {site_ip}/24 dev {interface}")
    run("sysctl -w net.ipv4.ip_forward=1")

    # Configure NAT
    run("iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE")
    run(f"iptables -A FORWARD -i {interface} -o eth0 -j ACCEPT")
    run(f"iptables -A FORWARD -i eth0 -o {interface} -m state --state RELATED,ESTABLISHED -j ACCEPT")

    # Launch dnsmasq
    print("\n🚀 Launching dnsmasq...")
    subprocess.Popen("dnsmasq -d -C dnsmasq.conf", shell=True)

    # Launch hostapd
    print("\n📡 Launching hostapd...")
    subprocess.Popen("hostapd hostapd.conf", shell=True)

    print(f"\n✅ Hotspot should now be active: SSID={ssid}, IP={site_ip}")
    time.sleep(3)

def kill_process(process_name):
    """Kills all processes matching a name, safely."""
    print(f"🔍 Checking for running '{process_name}' processes...")
    try:
        output = subprocess.check_output(f"pgrep -f {process_name}", shell=True).decode().strip().split('\n')
        for pid in output:
            if pid:
                try:
                    print(f"🛑 Killing {process_name} (PID {pid})")
                    os.kill(int(pid), signal.SIGTERM)
                except ProcessLookupError:
                    print(f"⚠️ Process {pid} already exited.")
    except subprocess.CalledProcessError:
        print(f"✅ No running '{process_name}' found")


def run(cmd, critical=True):
    print(f"\n🔧 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = result.stdout.decode().strip(), result.stderr.decode().strip()
    
    if result.returncode != 0:
        print(f"❌ Error: {err}")
        if critical:
            raise RuntimeError(f"Command failed: {cmd}")
    else:
        print(f"✅ Success: {out}")
    return result
