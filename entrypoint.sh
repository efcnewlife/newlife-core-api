#!/bin/bash

exec gunicorn -c gunicorn_conf.py "portal:app"
