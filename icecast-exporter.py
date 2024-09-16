import re
import requests
import xml.etree.ElementTree as ET
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import logging
from dotenv import load_dotenv
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("icecast_exporter.log"),  # Log to a file
        logging.StreamHandler()                       # Log to console
    ]
)

# Initialize a requests session for connection pooling
session = requests.Session()

# Define Prometheus metrics dictionaries
admin_metrics = {}
mountpoint_metrics = {}

# Function to clean up and validate metric names
def sanitize_metric_name(tag):
    # Remove XML namespace
    tag = re.sub(r'{.*}', '', tag)
    # Replace invalid characters with underscores
    tag = re.sub(r'\W|^(?=\d)', '_', tag)
    return tag.lower()

# Scrape mount-specific metrics from the XML page (/admin/stats.xsl)
def scrape_admin_stats_xsl(url, username, password, server_id):
    try:
        response = session.get(url, auth=(username, password), timeout=10)
        response.raise_for_status()  # Raise an error for bad HTTP status codes
    except requests.exceptions.RequestException as err:
        logging.error(f"Error fetching admin stats from {url} for {server_id}: {err}")
        return

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        logging.error(f"Error parsing XML from {url} for {server_id}: {e}")
        return

    # Per-mountpoint metrics (sources)
    for source in root.findall('.//source'):
        mount = source.get('mount')
        if mount is None:
            continue  # Skip sources without a mount

        mount_clean = sanitize_metric_name(mount.strip('/'))

        # Extract common metrics directly from tags
        mountpoint_metrics_to_extract = {
            'total_bytes_read': 'total_bytes_read',
            'total_bytes_sent': 'total_bytes_sent',
            'listener_peak': 'listener_peak',
            'listeners': 'listeners',
            'bitrate': 'bitrate',
            'channels': 'mpeg_channels',
            'samplerate': 'mpeg_samplerate',
        }

        for metric_name, tag in mountpoint_metrics_to_extract.items():
            element = source.find(tag)
            if element is not None and element.text is not None:
                try:
                    value = float(element.text)
                    full_metric_name = f'icecast_{server_id}_mount_{mount_clean}_{metric_name}'
                    if full_metric_name not in mountpoint_metrics:
                        mountpoint_metrics[full_metric_name] = Gauge(
                            full_metric_name,
                            f'Metric: {metric_name} for mount {mount_clean} on server {server_id}'
                        )
                    mountpoint_metrics[full_metric_name].set(value)

                    # Log and print the metric being scraped
                    log_message = f"[{server_id}] Mountpoint Metric scraped: {full_metric_name} = {value}"
                    logging.info(log_message)
                    print(log_message)
                except ValueError:
                    logging.warning(f"Non-numeric value found for {metric_name} on mount {mount_clean}: {element.text}")

        # Special handling for 'audio_info', which contains multiple metrics in a single string
        audio_info = source.find('audio_info')
        if audio_info is not None and audio_info.text:
            try:
                audio_params = dict(item.split('=') for item in audio_info.text.split(';'))
                samplerate = float(audio_params.get('ice-samplerate', 0))
                bitrate = float(audio_params.get('ice-bitrate', 0))
                channels = float(audio_params.get('ice-channels', 0))

                # Samplerate
                full_metric_name = f'icecast_{server_id}_mount_{mount_clean}_samplerate'
                if full_metric_name not in mountpoint_metrics:
                    mountpoint_metrics[full_metric_name] = Gauge(full_metric_name, f'Samplerate for mount {mount_clean} on server {server_id}')
                mountpoint_metrics[full_metric_name].set(samplerate)

                # Bitrate
                full_metric_name = f'icecast_{server_id}_mount_{mount_clean}_bitrate'
                if full_metric_name not in mountpoint_metrics:
                    mountpoint_metrics[full_metric_name] = Gauge(full_metric_name, f'Bitrate for mount {mount_clean} on server {server_id}')
                mountpoint_metrics[full_metric_name].set(bitrate)

                # Channels
                full_metric_name = f'icecast_{server_id}_mount_{mount_clean}_channels'
                if full_metric_name not in mountpoint_metrics:
                    mountpoint_metrics[full_metric_name] = Gauge(full_metric_name, f'Channels for mount {mount_clean} on server {server_id}')
                mountpoint_metrics[full_metric_name].set(channels)

                # Log parsed audio_info details
                logging.info(f"Parsed audio_info for {mount_clean}: samplerate={samplerate}, bitrate={bitrate}, channels={channels}")

            except Exception as e:
                logging.warning(f"Failed to parse audio_info for {mount_clean}: {e}")

# Scrape global stats from the Icecast admin page (XML)
def scrape_global_stats(url, username, password, server_id):
    try:
        # Fetch the admin page using requests with basic authentication
        response = requests.get(url, auth=(username, password), timeout=10)
        response.raise_for_status()  # Raise an error for bad HTTP status codes
    except requests.exceptions.RequestException as err:
        logging.error(f"Error fetching admin page from {url} for {server_id}: {err}")
        return

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        logging.error(f"Error parsing XML from {url} for {server_id}: {e}")
        return

    # Define a mapping of the metrics you want to extract from the XML
    metrics_mapping = {
        'client_connections': './/client_connections',
        'clients': './/clients',
        'connections': './/connections',
        'file_connections': './/file_connections',
        'listener_connections': './/listener_connections',
        'listeners': './/listeners',
        'source_relay_connections': './/source_relay_connections',
        'source_client_connections': './/source_client_connections',
        'source_total_connections': './/source_total_connections',
        'sources': './/sources',
        'stats': './/stats',
        'stats_connections': './/stats_connections'
    }

    # Extract and expose the metrics
    for metric_name, xpath in metrics_mapping.items():
        element = root.find(xpath)
        if element is not None and element.text is not None:
            try:
                value = float(element.text)
                full_metric_name = f'icecast_{server_id}_{metric_name}'
                if full_metric_name not in admin_metrics:
                    admin_metrics[full_metric_name] = Gauge(
                        full_metric_name, f'{metric_name} for server {server_id}'
                    )
                admin_metrics[full_metric_name].set(value)

                logging.info(f"[{server_id}] Global Metric scraped: {full_metric_name} = {value}")

            except ValueError:
                logging.warning(f"Non-numeric value found for {metric_name} on {server_id}: {element.text}")

# Custom HTTP request handler
class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            output = generate_latest()
            self.wfile.write(output)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

def run_http_server(port):
    server_address = ('', port)
    httpd = HTTPServer(server_address, MetricsHandler)
    logging.info(f"Prometheus metrics HTTP server started on port {port} on /metrics endpoint")
    httpd.serve_forever()

if __name__ == "__main__":
    # Load Icecast credentials and URLs from .env file
    icecast_admin_urls = os.getenv("ICECAST_ADMIN_URLS", "").split(',')
    usernames = os.getenv("ICECAST_USERNAMES", "").split(',')
    passwords = os.getenv("ICECAST_PASSWORDS", "").split(',')

    # Load the exporter port from the .env file, defaulting to 9300 if not set
    exporter_port = int(os.getenv("EXPORTER_PORT", "9300"))

    # Verify that all arrays have the same length
    if not (len(icecast_admin_urls) == len(usernames) == len(passwords)):
        logging.error("The number of Icecast admin URLs, usernames, and passwords must be the same")
        exit(1)

    # Start the HTTP server in a separate thread
    http_server_thread = threading.Thread(target=run_http_server, args=(exporter_port,))
    http_server_thread.daemon = True
    http_server_thread.start()

    while True:
        logging.info("Scraping Icecast stats from all servers...")
        for i, (admin_url, username, password) in enumerate(zip(icecast_admin_urls, usernames, passwords)):
            server_id = f"server_{i+1}"
            logging.info(f"Scraping metrics for {server_id}")

            # Fetch and parse mount-specific stats
            scrape_admin_stats_xsl(admin_url, username, password, server_id)

            # Fetch and parse global stats from the admin page
            scrape_global_stats(admin_url, username, password, server_id)

        time.sleep(15)

