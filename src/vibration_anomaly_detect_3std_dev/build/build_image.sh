#!bin/bash

sudo docker build --build-arg date=$(date -u +'%Y-%m-%dT%H:%M:%SZ') --tag vib_anomaly_detect_3std_dev_img:0.0.1 ../. 
