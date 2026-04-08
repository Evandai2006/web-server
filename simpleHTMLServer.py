import math
import socket
import threading
import time
import os

tz = 8#plz input timezone, BJS = UTC+8
max_threads = 50
active_clients = []
lock = threading.Lock()

r200 = b'HTTP/1.1 200 OK\n\n'
r304 = b'HTTP/1.1 304 Not Modified\n\n'
r400 = b'HTTP/1.1 400 Bad Request\n\nRequest Not Supported'
r403 = b'HTTP/1.1 403 Forbidden\n\nAccess Denied'
r404 = b'HTTP/1.1 404 Not Found\n\nFile Not Found'
r500 = b'HTTP/1.1 500 Internal Server Error\n\nAn error occurred.'


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

visit_blacklist = {'restricted.html'}
cli_whitelist = {'127.0.0.1'}

global file_mod_times
file_mod_times = {}

def get_file_mod_times():
    for filename in ['icon.png', 'root.html', 'page1.html', 'restricted.html']:
        file_path = os.path.join(BASE_DIR, filename)
        if os.path.isfile(file_path):
            file_mod_times[f'/{filename}'] = os.path.getmtime(file_path)
    print("File modified time refreshed")

def handle_client(client_connection, client_address):
    while True:
        request = client_connection.recv(1024).decode()
        get_file_mod_times()
        if not request:
            client_connection.sendall(r400)
            break

        print('Request:\n')
        print(request)

        try:
            headers = request.split('\n')
            if len(headers) == 0 or len(headers[0].split()) < 2:
                response = r400
            else:
                fields = headers[0].split()
                request_type = fields[0]
                filename = fields[1] if len(fields) > 1 else '/'

                if request_type == 'GET':
                    if filename.lstrip('/') in visit_blacklist and client_address[0] not in cli_whitelist:
                        response = r403
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
                                    if_modified_time += tz * 3600  # UTC+8 HKT ONLY, if you want to

                                    try:
                                        '''print(
                                            f'Comparing timestamps: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(if_modified_time))} >= {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(last_modified))}')  # Debug output
                                        print(
                                            f'Comparing timestamps: {if_modified_time} >= {last_modified}')  # Debug output'''

                                        if math.floor(if_modified_time) >= math.floor(last_modified):
                                            response = r304
                                            print(response)
                                            client_connection.sendall(response)
                                            return
                                    except ValueError as e:
                                        print(f"Could not parse If-Modified-Since date: {e}")
                                        continue
                        try:
                            with open(file_path, 'rb') as fin:
                                content = fin.read()
                                response_header = f'HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(content)}\nLast-Modified: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified))}\n\n'
                                response = response_header.encode() + content

                        except FileNotFoundError:
                            response = r404
                else:
                    response = r400

            print(response)
            client_connection.sendall(response)

        except Exception as e:
            print(f'Error while handling request: {e}')
            response = r500
            client_connection.sendall(response)

    client_connection.close()
    print(f'Client disconnected.')


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


if __name__ == "__main__":
    start_server()