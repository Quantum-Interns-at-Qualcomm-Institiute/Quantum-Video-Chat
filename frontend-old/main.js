// Start electron app

const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
// const io = require('socket.io-client');
const { Server } = require('socket.io')
// const path = require('path')

// const pythonScript = path.join(__dirname, 'video_chat.py');
// let port = 3000; 
// let server;

const createWindow = () => {
    const win = new BrowserWindow({
      width: 1440,
      height: 1024,
      webPreferences: {
        nodeIntegration: true, // Required for direct IPC communication
        contextIsolation: false, // Required for direct IPC communication
      }
    });

    win.loadFile('index.html');
}

app.whenReady().then(() => {
  // startServer();
  createWindow();
}).catch((err) => {
  console.error('Error:', err);
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})