const { app, BrowserWindow, ipcMain } = require('electron');
const isDev = require('electron-is-dev');
const path = require('node:path')

async function startSession(role) {
    console.log('STARTING A SESSION YAY')

    const {spawn} = require('child_process');
    const net = require('net');
    const PORT = 5001
    
    var client_server = net.createServer(function (conn) {
        console.log('Received connection from python subprocess')
        conn.write('Hello from Node.js')
    })

    client_server.listen(PORT, 'localhost')
    
    // spawn new child process to call the python script
    // const python = spawn('python3', [`../middleware/${role}.py`]);
    // TODO: INCLUDE PORT ARG FOR BEGINNING THE PYTHON PROCESS
    const python = spawn('python3', [`middleware/test.py`]);
        
    python.stdout.on('data', function (data) {
        console.log(data)
        console.log(data.toString())
        console.log()
        // dataToSend = data.toString();
    });

    python.stderr.on('data', function (data) {
        console.log(data)
        console.log(data.toString())
        console.log()
        // dataToSend = data.toString();
    });

    // in close event we are sure that stream from child process is closed
    python.on('close', (code) => {
        console.log(`child process close all stdio with code ${code}`);
        socket.destroy();
        // send data to browser
    });

    // HOW TO ENSURE PYTHON PROCESS IS KILLED WHEN ELECTRON DIES?

    return 'Started!'
}

function createWindow() {
    // Create the browser window.
    const win = new BrowserWindow({
        width: 800,
        height: 600,
        minWidth: 800,
        minHeight: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: true,
        },
    });

    // win.maximize();

    win.loadURL(
    isDev
        ? 'http://localhost:3000'
        : `file://${path.join(__dirname, '../build/index.html')}`
    );
    // Open the DevTools.
    if (isDev) {
        win.webContents.openDevTools({ mode: 'detach' });
    }


    // LISTEN FOR APP STUFF
    win.webContents.send('ipc', 'hello from main.js (to renderer)')
    ipcMain.on('ipc', (event, value) => {
        console.log('Received message: ' + value)
    })

}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
    ipcMain.handle('session:host', () => startSession('host'))
    ipcMain.handle('session:client', () => startSession('client'))
    createWindow()
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});