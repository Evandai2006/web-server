import math
import socket
import threading
import time
from datetime import datetime, timedelta
import os
import logging

'''USER PLEASE SET THESE PARAMETERS'''
tz = 8# UTC+8 is for HKT ONLY, if you want to use this from another time zone, pls change.
max_threads = 50#Max. # of threads running in the server
timeout_duration = 1#a maximum visit duration to the website, set according to need.
cleanup_time = 4#local time of auto clean up time(o'clock only, set within the timezone(tz))
TC_strategy = 'A'#A for only cleaning the threads once a day, B for queue(limited time session per client, AB for both.)
visit_blacklist = {'restricted.html'}
cli_whitelist = {}
'''================================'''



r200 = b'HTTP/1.1 200 OK\n\n'
r304 = b'HTTP/1.1 304 Not Modified\n\n'
r400 = b'HTTP/1.1 400 Bad Request\n\nRequest Not Supported'
r403 = b'HTTP/1.1 403 Forbidden\n\nAccess Denied'
r404 = b'HTTP/1.1 404 Not Found\n\nFile Not Found'


logging.basicConfig(
    level=logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    filename = 'server.log',
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
global file_mod_times
file_mod_times = {}
def get_file_mod_times():
    for filename in ['favicon.ico', 'root.html', 'page1.html', 'restricted.html','polyu.png']:
        file_path = os.path.join(BASE_DIR, filename)
        if os.path.isfile(file_path):
            file_mod_times[f'/{filename}'] = os.path.getmtime(file_path)
    print("File modified time refreshed")


active_clients = []
lock = threading.Lock()
timeout_duration *= 3600

class ClientThread:
    def __init__(self, client_connection, client_address):
        self.client_connection = client_connection
        self.client_address = client_address
        self.should_exit = threading.Event()#thread timeout flag
        self.start_time = time.time()#set start time of thread

def handle_client(client_thread):

    def close_connection():
        client_thread.client_connection.close()
        print("Connection terminated.\n")
        logging.info(f"Connection to client{client_thread.client_address} closed.")
        with lock:
            active_clients.remove(threading.current_thread())
            logging.info(f"Active thread{threading.current_thread()} removed. Current active thread count: {len(active_clients)}")

    logging.info(f"Connection from{client_thread.client_address} established.")

    while not client_thread.should_exit.is_set():
        if 'B' in TC_strategy:
            elapsed_time = time.time() - client_thread.start_time
            if elapsed_time > timeout_duration:
                print(f"Terminating client thread due to timeout: exceeding {elapsed_time / 3600:.2f} hours.")
                client_thread.should_exit.set()
                break#this management method isn't preferred for not crowded servers

        request = client_thread.client_connection.recv(1024).decode()

        if not request:
            client_thread.client_connection.sendall(r400)
            break

        get_file_mod_times()
        print('Request:\n')
        print(request)
        logging.info(f"Client requesting: {request}")

        try:
            headers = request.split('\n')
            if len(headers) == 0 or len(headers[0].split()) < 2:
                client_thread.client_connection.sendall(r400)
                print("Bad request, connection is to terminate.\n")
                logging.info(f"Server response: {r400}")
                break
            else:
                fields = headers[0].split()
                request_type = fields[0]
                filename = fields[1] if len(fields) > 1 else '/'

                if request_type == 'GET' or request_type == 'HEAD':
                    if filename.lstrip('/') in visit_blacklist and client_thread.client_address[0] not in cli_whitelist:
                        print(f"Response: {r403} MSG: Blacklisted file with unqualified client. Access denied. ")
                        logging.info(f"Server response: {r403}, MSG: Blacklisted file with unqualified client. Access denied.")
                        client_thread.client_connection.sendall(r403)
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
                                        client_thread.client_connection.sendall(r400)
                                        logging.info(f"Server response: {r400}\nERR MSG: {e}")
                                        break
                        else:
                            try:
                                with open(file_path, 'rb') as fin:
                                    content = fin.read()
                                    if filename.endswith('.png'):
                                        response_header = f'HTTP/1.1 200 OK\nContent-Type: image/png\nContent-Length: {len(content)}\nLast-Modified: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified))}\n\n'
                                    elif filename.endswith('.webp'):
                                        response_header = f'HTTP/1.1 200 OK\nContent-Type: image/webp\nContent-Length: {len(content)}\nLast-Modified: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified))}\n\n'
                                    elif filename.endswith('.jpeg') or filename.endswith('.jpg'):
                                        response_header = f'HTTP/1.1 200 OK\nContent-Type: image/jpg\nContent-Length: {len(content)}\nLast-Modified: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified))}\n\n'
                                    else:
                                        response_header = f'HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(content)}\nLast-Modified: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified))}\n\n'

                                    if request_type == 'HEAD':
                                        response = response_header.encode()
                                    else:
                                        response = response_header.encode() + content

                            except FileNotFoundError:
                                client_thread.client_connection.sendall(r404)
                                print(f"Response: {r404}, connection is to terminate.\n")
                                break

                else:
                    client_thread.client_connection.sendall(r400)
                    print("Bad request, connection is to terminate.\n")
                    logging.info(f"Server response: {r400}, unsupported connection type.")
                    break

            print(response)
            client_thread.client_connection.sendall(response)
            logging.info(f"Server response: {response}")

            if 'close' in headers[2]:
                break

        except Exception as e:
            print(f'Error while handling request: {e}, connection is to terminate.\n')
            response = r400
            print(response)
            client_thread.client_connection.sendall(response)
            logging.info(f"Server response: {r400}\nERR MSG: {e}")
            break

    close_connection()

def reset_connections():#terminate all the threads at set time to free server resources.
    while True:
        if 'A' in TC_strategy:
            now = datetime.utcnow()
            nextrun = now.replace(hour=cleanup_time, minute=0, second=0, microsecond=0) + timedelta(hours=24-tz)
            sleeptime = (nextrun - now).total_seconds()
            time.sleep(sleeptime)
            cleanup_timeout = 120
            print(f"Resetting connections... Est. waiting time: {cleanup_timeout} sec.")
            with lock:
                for thread in active_clients:
                    if thread.is_alive():
                        if thread.start_time - time.time() > timeout_duration:#to avoid that user happen to just established the thread
                            thread.should_exit.set()#set exit flag to the thread
                            thread.join(timeout = cleanup_timeout)
                            active_clients.remove(thread)
                print(f"Process completed. {len(active_clients)} threads remaining, due to: thread running time below minimum. remaining thread(s): {active_clients}")
                logging.info(f"Threads cleared at set time. {len(active_clients)} threads remaining, due to: thread running time below minimum. remaining thread(s): {active_clients}")

def thread_mgmt():
    SERVER_HOST = 'localhost'
    SERVER_PORT = 8080

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(1024)
    print('Listening on port %s ...' % SERVER_PORT)

    threading.Thread(target=reset_connections, daemon=True).start()#start the auto reset daemon

    while True:
        client_connection, client_address = server_socket.accept()
        print(f'Connection from {client_address}')
        with lock:
            if max_threads > len(active_clients):
                client_thread = ClientThread(client_connection, client_address)
                thread = threading.Thread(target=handle_client, args=(client_thread,))
                active_clients.append(thread)
                thread.start()
            else:
                logging.info(f'Refused connection from {client_address}, ERR MSG: Too much threads established.')
                print("CAUTION:Max client connections reached. Connection refused.\nIf the server is facing hi traffic, change the thread control strategy?")
        print(f"Threading control: {TC_strategy}\ncurrent running threads: {active_clients}")


if __name__ == "__main__":
    thread_mgmt()