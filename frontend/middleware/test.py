import time
import socket

PORT = 5001

## peer_sock = socket.socket()
client_sock = socket.socket()
client_sock.connect(('127.0.0.1',PORT))

data = client_sock.recv(1024)
print('Python client received and printing ' + str(data))
client_sock.sendall(('Python client received and returning ' + str(data)).encode('UTF-8'))

client_sock.close()
