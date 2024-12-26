import socket
import time

def check_postgres_port_open(host, port, retries=5, delay=2):
    """
    Checks if the PostgreSQL port is open by attempting to create a socket connection.
    If the connection attempt fails, it waits for 'delay' seconds and retries.
    
    :param host: The hostname or IP address of the PostgreSQL server.
    :param port: The port number of the PostgreSQL server.
    :param retries: Maximum number of retries.
    :param delay: Delay in seconds between retries.
    :return: True if the port is open, False otherwise.
    """
    for attempt in range(retries):
        try:
            with socket.create_connection((host, port), timeout=10):
                print(f"Connection to PostgreSQL on port {port} successful.")
                return True
        except (socket.timeout, ConnectionRefusedError):
            print(f"Connection to PostgreSQL on port {port} failed. Attempt {attempt + 1} of {retries}.")
            time.sleep(delay)
    return False
