#!/bin/bash
# Load environment variables from the .env file
source /your/path/to/.env
# Start the exporter
exec /usr/bin/python3 /path/to/your/icecast-exporter.py
