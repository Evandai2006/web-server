import math
import socket
import threading
import time
import os
import logging

tz = 8# UTC+8 HKT ONLY, if you want to use this from another time zone, pls change.
max_threads = 50
active_clients = []
lock = threading.Lock()

r200 = b'HTTP/1.1 200 OK\n\n'
r304 = b'HTTP/1.1 304 Not Modified\n\n'
r400 = b'HTTP/1.1 400 Bad Request\n\nRequest Not Supported'
r403 = b'HTTP/1.1 403 Forbidden\n\nAccess Denied'
r404 = b'HTTP/1.1 404 Not Found\n\nFile Not Found'


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

visit_blacklist = {'restricted.html'}
cli_whitelist = {}

global file_mod_times
file_mod_times = {}

logging.basicConfig(
    level=logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    filename = 'server.log',
)

def get_file_mod_times():
    for filename in ['favicon.ico', 'root.html', 'page1.html', 'restricted.html','polyu.png']:
        file_path = os.path.join(BASE_DIR, filename)
        if os.path.isfile(file_path):
            file_mod_times[f'/{filename}'] = os.path.getmtime(file_path)
    print("File modified time refreshed")

def handle_client(client_connection, client_address):

    def close_connection():
        client_connection.close()
        print("Connection terminated.\n")
        logging.info(f"Connection to client{client_address} closed.")
        with lock:
            active_clients.remove(threading.current_thread())
            logging.info(f"Active thread{threading.current_thread()} removed. Current active thread count: {len(active_clients)}")

    logging.info(f"Connection from{client_address} established.")

    while True:
        request = client_connection.recv(1024).decode()
        get_file_mod_times()
        if not request:
            client_connection.sendall(r400)
            break

        print('Request:\n')
        print(request)
        logging.info(f"Client requesting: {request}")

        try:
            headers = request.split('\n')
            if len(headers) == 0 or len(headers[0].split()) < 2:
                client_connection.sendall(r400)
                print("Bad request, connection is to terminate.\n")
                logging.info(f"Server response: {r400}")
                break
            else:
                fields = headers[0].split()
                request_type = fields[0]
                filename = fields[1] if len(fields) > 1 else '/'

                if request_type == 'GET':
                    if filename.lstrip('/') in visit_blacklist and client_address[0] not in cli_whitelist:
                        client_connection.sendall(r403)
                        break
                    else:
                        if filename == '/':
                            filename = '/root.html'
                        file_path = os.path.join(BASE_DIR, filename.lstrip('/'))
                        last_modified = file_mod_times.get(filename, time.time())
                        if 'If-Modified-Since:' in request:
                            for header in headers:
                                if header.startswith("If-Modified-Since:"):
                                    if_modified_since = header.split(': ')[1].strip()
                                    if_modified_time = time.mktime(
                                        time.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S GMT'))
                                    if_modified_time += tz * 3600

                                    try:
                                        if math.floor(if_modified_time) >= math.floor(last_modified):
                                            response = r304
                                    except ValueError as e:
                                        print(f"Could not parse If-Modified-Since date: {e}, connection is to terminate.\n.")
                                        client_connection.sendall(r400)
                                        logging.info(f"Server response: {r400}\nERR MSG: {e}")
                                        break
                        else:
                            try:
                                with open(file_path, 'rb') as fin:
                                    content = fin.read()
                                    if filename.endswith('.png'):
                                        response_header = f'HTTP/1.1 200 OK\nContent-Type: image/png\nContent-Length: {len(content)}\nLast-Modified: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified))}\n\n'
                                    else:
                                        response_header = f'HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(content)}\nLast-Modified: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified))}\n\n'
                                    response = response_header.encode() + content

                            except FileNotFoundError:
                                client_connection.sendall(r404)
                                print(f"Response: {r404}, connection is to terminate.\n")
                                break

                else:
                    client_connection.sendall(r400)
                    print("Bad request, connection is to terminate.\n")
                    logging.info(f"Server response: {r400}, unsupported connection type.")
                    break



            print(response)
            client_connection.sendall(response)
            logging.info(f"Server response: {response}")

            if 'keep-alive' in headers[2]:
                continue
            else:
                break

        except Exception as e:
            print(f'Error while handling request: {e}, connection is to terminate.\n')
            response = r400
            print(response)
            client_connection.sendall(response)
            logging.info(f"Server response: {r400}\nERR MSG: {e}")
            break

    close_connection()


def start_server():
    SERVER_HOST = 'localhost'
    SERVER_PORT = 8080

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(1024)
    print('Listening on port %s ...' % SERVER_PORT)

    while True:
        client_connection, client_address = server_socket.accept()
        print(f'Connection from {client_address}')

        with lock:
            if len(active_clients) < max_threads:
                thread = threading.Thread(target=handle_client, args=(client_connection,client_address))
                active_clients.append(thread)
                thread.start()
            else:
                print('Max client connections reached. Connection refused.')
                logging.info(f'Refused connection from {client_address}, reason: max client connections reached.')


if __name__ == "__main__":
    start_server()