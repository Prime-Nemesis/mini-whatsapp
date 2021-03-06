import datetime
import os
import re
import socket
import threading, time
import tqdm
from cryptography.fernet import Fernet

PORT = 9999
flag = False
DISCONNECT_MSG = '!EXIT'
FILE_MSG = 'FILE'
UPLOAD_MSG = 'UPLOAD'
DOWNLOAD_MSG = 'DOWNLOAD'
LIST_MSG = 'LIST'
PVT_MSG = 'PVT'
FILE_NAME = ''
FILE_SIZE = ''
BUF_SIZE = 1024
# SERVER_IP = socket.gethostbyname(socket.gethostname())
SERVER_IP = 'localhost'
ADDR = (SERVER_IP, PORT)

while True:
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    name = input("Enter your name: ")
    print(f'[CONNECTING] To {SERVER_IP}:{PORT}')
    client.connect(ADDR)
    client.send(name.encode())
    access_recv = client.recv(BUF_SIZE).decode()
    print(access_recv)
    if 'GRANTED' in access_recv:
        break
    
    client.close()

print(f"[JOINED SUCESSFULLY], Name: {name}")


def make_dirs():
    if not os.path.exists('client_files'):
        # directory to store files downloaded from server
        os.makedirs('client_files')


def gen_key():
    """
    Generates a key and save it into a file
    """
    key = Fernet.generate_key()
    return key


def send_allbytes(sock, data, flags=0):
    nbytes = sock.send(data, flags)
    if nbytes > 0:
        return send_allbytes(sock, data[nbytes:], flags)
    else:
        return None


def send_pvt_msg(msg):
    _, rec_name, pvt_msg = msg.split(' ',2)
    curr_time = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    pvt_msg_to_send = f"[PRIVATE][{curr_time}] {name}: {pvt_msg}"
    key = gen_key()
    f = Fernet(key)
    encr_packet = '#'.join([key.decode(), f.encrypt(pvt_msg_to_send.encode()).decode()])
    temp = f'PVT {rec_name} {encr_packet}'
    send_allbytes(client, temp.encode())


def send_msg(msg):
    curr_time = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    msg_to_send = f"[{curr_time}] {name}: {msg}"
    key = gen_key()
    f = Fernet(key)
    encr_packet = '#'.join([key.decode(), f.encrypt(msg_to_send.encode()).decode()])
    send_allbytes(client, encr_packet.encode())


def receive_msg():
    while True:
        global flag
        global FILE_NAME
        global FILE_SIZE
        message_recv = client.recv(BUF_SIZE).decode()
        if not bool(re.match('\[(.*?)\]', message_recv)):
            key, encr_msg = message_recv.split('#')
            f = Fernet(key.encode())
            message_recv = f.decrypt(encr_msg.encode()).decode()
        print(message_recv)
        if 'UPLOAD' in message_recv:
            STATUS = re.findall(r'\d+', message_recv)[0]

            if STATUS == '1':
                print("Uploading.....")

                NUM_CHUNKS = int(FILE_SIZE) // BUF_SIZE + 1

                # Progress bar
                progress = tqdm.tqdm(range(FILE_SIZE), desc=f"Sending {FILE_NAME}", unit="B", unit_scale=True,
                                    unit_divisor=1024)

                with open(FILE_NAME, "rb") as file:
                    for i in range(NUM_CHUNKS):
                        chunk = file.read(BUF_SIZE)
                        if not chunk:
                            break
                        key = gen_key()
                        f = Fernet(key)
                        encr_packet = '#'.join([key.decode(), f.encrypt(chunk).decode()]).encode()
                        if i == 0:
                            packet_size = len(encr_packet)
                            client.send(str(packet_size).encode())
                            time.sleep(0.5)
                        send_allbytes(client, encr_packet)
                        # Update the progress bar
                        progress.update(len(chunk))
                    progress.close()
                flag = False
            else:
                print("Upload Failed")
                flag = False

        elif 'DOWNLOAD' in message_recv:
            FILE_SIZE = re.findall(r'\d+', message_recv)[0]

            if int(FILE_SIZE) != 0:
                print("Downloading.....")

                NUM_CHUNKS = int(FILE_SIZE) // BUF_SIZE + 1
                packet_size = client.recv(BUF_SIZE).decode()

                # Progress bar
                progress = tqdm.tqdm(range(int(FILE_SIZE)), desc=f"Recieving {FILE_NAME}", unit="B", unit_scale=True,
                                    unit_divisor=1024)

                with open('client_files/' + FILE_NAME, "wb") as file:
                    for i in range(NUM_CHUNKS):
                        chunk = client.recv(int(packet_size)).decode()
                        if not chunk:
                            break
                        key, encr_msg = chunk.split('#')
                        f = Fernet(key.encode())
                        decr_chunk = f.decrypt(encr_msg.encode())
                        file.write(decr_chunk)
                        # Update the progress bar
                        progress.update(len(decr_chunk))
                    progress.close()

                print(f"File {FILE_NAME} Received")
                flag = False
            else:
                # requested file does not exist
                print("Download Failed")
                flag = False


thread = threading.Thread(target=receive_msg, daemon=True)
thread.start()

while True:
    message = input()

    if message == DISCONNECT_MSG:
        client.send(message.encode())
        client.close()
        break

    elif message.startswith(UPLOAD_MSG):

        _, FILE_NAME = message.split(' ')
        try:
            FILE_SIZE = os.path.getsize(FILE_NAME)
            message = f"{message} {FILE_SIZE}"
            client.send(message.encode())
            flag = True
            while (flag):
                continue
        except OSError:
            print("The file you tried to upload does not exist, Please check")

    elif message.startswith(DOWNLOAD_MSG):
        make_dirs()
        client.send(message.encode())
        _, FILE_NAME = message.split(' ')
        flag = True
        while (flag):
            continue

    elif message.startswith(LIST_MSG):
        client.send(message.encode())

    elif message.startswith(PVT_MSG):
        send_pvt_msg(message)

    else:
        send_msg(message)
