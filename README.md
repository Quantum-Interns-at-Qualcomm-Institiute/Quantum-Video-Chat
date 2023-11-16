# Peer-to-Peer Chat Demo
with Server, Clients, Sockets, and APIs
  
## Running Locally
Begin in root directory.  
Install all necessary packages with `pip`.

### Server
Server API will automatically listen on http://localhost:5000.

`cd server; python3 api.py`

### Client
Client API will automatically listen on http://localhost:4000.  
WebSocket API will automatically listen on http://localhost:3000.

If endpoints are in use, Client will attempt to listen on next available port in increasing order.

`cd client; python3 client.py`
