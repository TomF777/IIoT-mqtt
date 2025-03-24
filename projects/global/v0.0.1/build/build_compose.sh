#!/bin/bash

title()
{
green=`tput setaf 2`
reset=`tput sgr0`

echo ""
echo ""
echo "${green}**********************$1**********************${reset}"
echo ""
echo ""
sleep 1s 
}

info_flat()
{
green=`tput setaf 2`
reset=`tput sgr0`

echo "${green} $1 ${reset}"
sleep 1s 
}


info_enter()
{
green=`tput setaf 2`
reset=`tput sgr0`

echo ""
echo "${green} $1 ${reset}"
sleep 1s 
}

info_enter "Do you want continue deploy Grafana, Influx, MQtt and portainer? It will remove all previous data of old deployment of it [Y/N]:"
read stdin

if [[ $stdin == [Nn] ]]; then
    echo "Exiting"
    exit
fi

if [[ $stdin != [YyNn] ]]; then
    echo "Invalid input, exiting"
    exit
fi


########################################################
title "CREATING CATALOGS"

info_flat  "Create /OI/Apps_data/Global/Influx"
mkdir -p /OI/Apps_data/Global/Influx

info_flat  "Create /OI/Apps_data/Global/Grafana"
mkdir -p /OI/Apps_data/Global/Grafana

info_flat "Create /OI/Apps_data/Global/Mqtt"
mkdir -p /OI/Apps_data/Global/Mqtt

info_flat "Create /OI/Apps_data/Global/Portainer"
mkdir -p /OI/Apps_data/Global/Portainer


########################################################
title  "COPY CATALOGS"

info_flat "Copy InfluxDB config, data catalogs to /OI/Apps_data/Global/Influx"
cp -r ../catalogs/InfluxDB/config /OI/Apps_data/Global/Influx
cp -r ../catalogs/InfluxDB/data /OI/Apps_data/Global/Influx

info_flat "Copy Grafana etc, var catalogs to /OI/Apps_data/Global/Grafana"
cp -r ../catalogs/Grafana/etc /OI/Apps_data/Global/Grafana
cp -r ../catalogs/Grafana/var /OI/Apps_data/Global/Grafana

info_flat  "Copy Mqtt config, data, log catalogs to /OI/Apps_data/Global/Grafana"
cp -r ../catalogs/Mqtt/config /OI/Apps_data/Global/Mqtt
cp -r ../catalogs/Mqtt/data /OI/Apps_data/Global/Mqtt
cp -r ../catalogs/Mqtt/log /OI/Apps_data/Global/Mqtt

info_flat  "Copy Portainer  data catalog to /OI/Apps_data/Global/Portainer"
cp -r ../catalogs/Portainer/data /OI/Apps_data/Global/Portainer

info_enter  "Set permision for all catalogs in /OI/Apps_data/Global/Influx on 777"
chmod -R 777 /OI/Apps_data/Global/Influx

info_flat  "Set permision for all catalogs in /OI/Apps_data/Global/Grafana on 777"
chmod -R 777 /OI/Apps_data/Global/Grafana

info_flat  "Set permision for all catalogs in /OI/Apps_data/Global/Mqtt on 777"
chmod -R 777 /OI/Apps_data/Global/Mqtt

info_flat  "Set permision for all catalogs in /OI/Apps_data/Global/Portainer on 777"
chmod -R 777 /OI/Apps_data/Global/Portainer

########################################################
title "IMPORT IMAGES TO DOCKER"

info_flat "Import grafana v9.2.4"
docker load < ../images/grafana_9_2_4.tar

info_flat "Import influxdb v2.2.0"
docker load < ../images/influxdb_2_2_0.tar

info_flat "Import mosquitto mqtt v2.0.15"
docker load < ../images/mosquitto_2_0_15.tar

info_flat "Import portainer v2.18.3"
docker load < ../images/portainer_2_18_3.tar


########################################################
title  "DEPLOY PROJECT"

info_enter "Create IOT_Network_Global network"
docker network create IOT_Network_Global

info_enter "Up docker compose with name 'global"
docker compose -p "global" -f ../global_v1.2.0.yml up -d --no-recreate


######################################################
title  "!!!!! INSTALL COMPLETE, CONGRATULATIONS !!!!!"


sleep 1s

