#!/bin/bash

apt-get install -y python3
apt-get install -y python3-pip
apt-get install -y postgresql
apt-get install -y python3-psycopg2
apt-get install -u libpq-dev

pip3 install watchdog
