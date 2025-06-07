#!/bin/bash

INTERFACE="wlan0"

echo "🔌 Killing any host dnsmasq..."
sudo pkill -f dnsmasq

echo "🔌 Stopping wpa_supplicant and NetworkManager (if running)..."
sudo systemctl stop wpa_supplicant 2>/dev/null || echo "⏭️ wpa_supplicant not running"
sudo systemctl stop NetworkManager 2>/dev/null || echo "⏭️ NetworkManager not running"

echo "📡 Unblocking WiFi with rfkill..."
sudo rfkill unblock wifi

echo "🔍 Checking current mode of $INTERFACE..."
TYPE=$(iw dev $INTERFACE info | grep "type" | awk '{print $2}')

if [ "$TYPE" = "managed" ]; then
  echo "⚠️  $INTERFACE is in mode 'managed'. Switching to '__ap' mode..."
  sudo ip link set $INTERFACE down
  sudo iw dev $INTERFACE set type __ap
  sudo ip link set $INTERFACE up
  sleep 1
  TYPE=$(iw dev $INTERFACE info | grep "type" | awk '{print $2}')
  if [ "$TYPE" != "__ap" ]; then
    echo "❌ Failed to set $INTERFACE to '__ap' mode. Exiting."
    exit 1
  fi
  echo "✅ $INTERFACE is now in '__ap' mode."

elif [ "$TYPE" = "AP" ]; then
  echo "✅ $INTERFACE is already in 'AP' mode. Continuing without change."

elif [ "$TYPE" = "__ap" ]; then
  echo "✅ $INTERFACE is already in '__ap' mode. Ready for hotspot."

else
  echo "⚠️  Unknown mode '$TYPE'. Attempting to set '__ap' anyway..."
  sudo ip link set $INTERFACE down
  sudo iw dev $INTERFACE set type __ap
  sudo ip link set $INTERFACE up
  sleep 1
  TYPE=$(iw dev $INTERFACE info | grep "type" | awk '{print $2}')
  if [ "$TYPE" != "__ap" ]; then
    echo "❌ Failed to force set $INTERFACE to '__ap' mode. Exiting."
    exit 1
  fi
  echo "✅ $INTERFACE is now in '__ap' mode."
fi

# echo "🚀 Starting hotspot container..."
# sudo docker run --rm -it \
#   --network=host \
#   --privileged \
#   --device=/dev/spidev0.0 \
#   --device=/dev/gpiomem \
#   --name hotspot-app \
#   vova0911/lora:arm64_1.0.0


echo "🚀 Starting hotspot via Docker Compose..."
sudo docker compose up --force-recreate