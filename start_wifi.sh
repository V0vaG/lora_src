#!/bin/bash

INTERFACE="wlan0"

echo "🔌 Killing any host dnsmasq..."
sudo pkill -f dnsmasq

echo "🔍 Checking if $INTERFACE is in AP mode..."
TYPE=$(iw dev $INTERFACE info | grep "type" | awk '{print $2}')

if [ "$TYPE" != "__ap" ]; then
  echo "⚠️  $INTERFACE is in mode '$TYPE'. Switching to '__ap' mode..."
  sudo nmcli radio wifi off 2>/dev/null
  sudo rfkill unblock wifi
  sudo ip link set $INTERFACE down
  sudo iw dev $INTERFACE set type __ap
  sudo ip link set $INTERFACE up
  sleep 1
  TYPE=$(iw dev $INTERFACE info | grep "type" | awk '{print $2}')
  if [ "$TYPE" != "__ap" ]; then
    echo "❌ Failed to set $INTERFACE to AP mode. Exiting."
    exit 1
  fi
  echo "✅ $INTERFACE is now in AP mode."
else
  echo "✅ $INTERFACE is already in AP mode."
fi

echo "🚀 Starting hotspot container..."
sudo docker run --rm -it \
  --network=host \
  --privileged \
  --device=/dev/spidev0.0 \
  --device=/dev/gpiomem \
  --name hotspot-app \
  vova0911/lora:arm64_1.0.0
