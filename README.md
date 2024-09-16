# Icecast Prometheus Exporter

An exporter for Icecast server statistics, designed to expose metrics for Prometheus monitoring. This tool collects and exports server-wide and mountpoint-specific Icecast stats such as listeners, bytes read/sent, client connections, and more.

## Features

- Exports global server statistics like total client connections, listener counts, and source connections.
- Exports detailed mountpoint-specific statistics such as listeners, bytes sent/read, bitrate, and samplerate.
- Integration with Prometheus for real-time monitoring and alerting.
- Grafana-ready for advanced visualization.
- Configurable via `.env` file and systemd service.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Prometheus Setup](#prometheus-setup)
4. [Grafana Dashboard](#grafana-dashboard)
5. [Systemd Setup](#systemd-setup)
6. [License](#license)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/icecast-exporter.git
   cd icecast-exporter
2. Install dependancies
   ```bash
   pip install -r requirements.txt

3. Set up the .env file to include your icecast server details:
   ```bash
   cp .env.example .env
Edit the .env file to configure the icecast server details:
   ```bash
   EXPORTER_PORT=9300
   ICECAST_ADMIN_URLS=http://your-icecast-server.com/admin/stats.xsl
   ICECAST_USERNAMES=yourusername
   ICECAST_PASSWORDS=yourpassword
   ```
## Run the Exporter locally
   ```bash
   python icecast-exporter.py
   ```
The exporter will start on the configured port (default of 9300)

## Prometheus setup

To monitor icecast stats in Prometheus, add the following scrape configuration to your prometheus.yml file:
   ```
   scrape_configs:
  - job_name: 'icecast_exporter'
    static_configs:
      - targets: ['localhost:9300']  # Replace with your server and port if needed
   ```
 Reload Prometheus after making changes

   ```bash
   sudo systemctl reload prometheus
   ```
## Grafana Dashboard
To visualize your Icecast metrics in Grafana:

Add Prometheus as a data source in Grafana (Settings > Data Sources > Prometheus).

Create a new dashboard and add panels with queries such as:

   ```icecast_server_1_listeners:``` Current number of listeners.

   ```icecast_server_1_total_bytes_sent:``` Total bytes sent to listeners.

   ```icecast_server_1_mount_output_128_mp3_listeners:``` Listeners for a specific mountpoint.

You can customize the visualization to suit your needs, including setting up alerts for critical metrics.

## SystemD Setup
For continuous running in the background, you can set up a systemd service.
1. Create a service file:
   ```sudo vi /etc/systemd/system/icecast-exporter.service```
2. Add the following content:

   ``` bash
   [Unit]
   Description=Icecast Prometheus Exporter Service
   After=network.target

   [Service]
   Type=simple
   User=your_username
   WorkingDirectory=/path/to/your/exporter
   ExecStart=/usr/bin/python3 /path/to/your/exporter/icecast-exporter.py
   EnvironmentFile=/path/to/your/exporter/.env # if you get an error about .env file missing, use the start-exporter.sh here and put the path to your .env file path into the .sh script
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   
4. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable icecast-exporter
   sudo systemctl start icecast-exporter
   ```
5. Check the status
   ```bash
   sudo systemctl status icecast-exporter
   ```

   
