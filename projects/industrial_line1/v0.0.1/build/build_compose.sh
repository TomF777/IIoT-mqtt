#!/bin/bash

title "Deploy compose project for industrial line 1 "

docker compose --env-file ../industrial_line_v0.0.1.env -f ../industrial_line_v0.0.1.yml -p "industrial_line1" up -d
