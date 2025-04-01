#!bin/bash

sudo docker build --build-arg date=$(date -u +'%Y-%m-%dT%H:%M:%SZ') --tag temp_humid_monitor_img:0.0.1 ../. 
