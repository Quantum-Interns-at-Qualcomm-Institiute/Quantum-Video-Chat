// Start electron app

const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const io = require('socket.io-client');


function connectToServer(port) {
  const url = `http://localhost:${port}`;
  console.log(`Trying to connect to server: ${url}`);
  const socket = io(url);

  socket.on('connect', () => {
    console.log('Connected to server!');
  });

  socket.on('disconnect', () => {
    console.log('Disconnected from server!');
  });

  return socket;
}

let port = 3000; 

function startSocketConnection() {
  const socket = connectToServer(port);

  socket.on('connect_error', () => {
    console.log(`Connection failed on port ${port}. Trying next port...`);
    port++;
    startSocketConnection(); // Retry with incremented port
  });

  return socket;
}

// Start the socket connection
const socket = startSocketConnection();

const pythonScript = path.join(__dirname, 'video_chat.py');

const createWindow = () => {
    const win = new BrowserWindow({
      width: 1440,
      height: 1024
    })
  
    win.loadFile('index.html');
}

app.whenReady().then(() => {
    createWindow()
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})