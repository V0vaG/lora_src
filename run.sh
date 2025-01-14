#!/bin/bash

sudo docker build -t flask-lora-app .

sudo docker run --privileged \
  --device /dev/spidev0.0 \
  --device /dev/spidev0.1 \
  --device /dev/gpiomem \
  -p 5000:5000 \
  flask-lora-app

