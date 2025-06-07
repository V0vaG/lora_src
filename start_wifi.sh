#!/bin/bash
echo "🔌 Killing any host dnsmasq..."
sudo pkill -f dnsmasq

echo "🚀 Starting hotspot container..."
sudo docker run --rm -it \
  --network=host \
  --privileged \
  --device=/dev/spidev0.0 \
  --device=/dev/gpiomem \
  --name hotspot-app \
  vova0911/lora:armhf_1.0.0
