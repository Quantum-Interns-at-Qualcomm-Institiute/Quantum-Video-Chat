const { app, BrowserWindow, ipcMain } = require('electron');
const isDev = require('electron-is-dev');
const path = require('node:path')


async function startSession(role) {
    // console.log('STARTING A SESSION YAY')
    // const PORT = 5001

    const {spawn} = require('child_process');
    // const io = require('socket.io')(PORT);

    // io.on('connection', function(socket) {
    //     console.log('Received a connection to the frontend socket')

        
    // })
    // const net = require('net');
    
    // var client_server = net.createServer(function (conn) {
    //     console.log('Received connection from python subprocess')
    //     conn.write('Hello from Node.js')
    // })

    // client_server.listen(PORT, 'localhost')
    
    // spawn new child process to call the python script
    // const python = spawn('python3', [`../middleware/${role}.py`]);
    // TODO: INCLUDE PORT ARG FOR BEGINNING THE PYTHON PROCESS
    const python = spawn('python3', [`middleware/video_chat.py`]);
        
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
        // socket.destroy();
        // send data to browser
    });

    // HOW TO ENSURE PYTHON PROCESS IS KILLED WHEN ELECTRON DIES?

    // return 'Started!'
}

function createWindow() {
    const PORT = 5001;

    const { spawn } = require('child_process');
    const io = require('socket.io')(PORT);

    const win = new BrowserWindow({
        width: 800,
        height: 600,
        minWidth: 800,
        minHeight: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: true, // Required for direct IPC communication
            contextIsolation: false, // Required for direct IPC communication
        }
    });

    win.loadURL(
    isDev
        ? 'http://localhost:3000'
        : `file://${path.join(__dirname, '../src/index.html')}`
    );

    // Whenever we receive a socket connection from the child process
    io.on('connection', (socket) => {
        console.log('Received a socket connection from the python child');

        // 'stream' events are accompanied by frame, a bytes object representing an isvm from our python script
        socket.on('stream', (frame) => {

            // Convert bytes to blob
            const frameBlob = new Blob(frame, { type : 'plain/text' });

            // Use promise-based .arrayBuffer() method so we can bypass having a FileReader
            frameBlob.arrayBuffer().then( (frameBuffer) => {
                const videoFrame = new VideoFrame(frameBuffer);

                // Send this frame to the other window
                win.webContents.send('frame', videoFrame)
            }).catch( (err) => {
                console.error(err);
            })
        })
    })


}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
    // ipcMain.handle('session:host', () => startSession('host'))
    // ipcMain.handle('session:client', () => startSession('client'))
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