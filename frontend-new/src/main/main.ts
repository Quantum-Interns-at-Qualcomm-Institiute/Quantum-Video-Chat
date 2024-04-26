/* eslint global-require: off, no-console: off, promise/always-return: off */

/**
 * This module executes inside of electron's main process. You can start
 * electron renderer process from here and communicate with the other processes
 * through IPC.
 *
 * When running `npm run build` or `npm run build:main`, this file is compiled to
 * `./src/main.js` using webpack. This gives us some performance wins.
 */
import path from 'path';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { app, BrowserWindow, shell, ipcMain, ipcRenderer } from 'electron';
import { autoUpdater } from 'electron-updater';
import log from 'electron-log';
import MenuBuilder from './menu';
import { resolveHtmlPath } from './util';

class AppUpdater {
  constructor() {
    log.transports.file.level = 'info';
    autoUpdater.logger = log;
    autoUpdater.checkForUpdatesAndNotify();
  }
}

let mainWindow: BrowserWindow | null = null;

// ipcMain.on('ipc-example', async (event, arg) => {
//   const msgTemplate = (pingPong: string) => `IPC test: ${pingPong}`;
//   console.log(msgTemplate(arg));
//   event.reply('ipc-example', msgTemplate('pong'));
// });

if (process.env.NODE_ENV === 'production') {
  const sourceMapSupport = require('source-map-support');
  sourceMapSupport.install();
}

// const isDebug =
// process.env.NODE_ENV === 'development' || process.env.DEBUG_PROD === 'true';

const isDebug = false;

if (isDebug) {
  require('electron-debug')();
}

const installExtensions = async () => {
  const installer = require('electron-devtools-installer');
  const forceDownload = !!process.env.UPGRADE_EXTENSIONS;
  const extensions = ['REACT_DEVELOPER_TOOLS'];

  return installer
    .default(
      extensions.map((name) => installer[name]),
      forceDownload,
    )
    .catch(console.log);
};

const createWindow = async () => {
  const PORT = 5001;
  const io = require('socket.io')(PORT);

  const { spawn } = require('child_process');
  const python = spawn('python3', [`src/middleware/video_chat.py`, [PORT]]);

  // python.stdout.on('data', function (data) {
  //   console.log(data);
  //   console.log(data.toString());
  //   console.log();
  //   // dataToSend = data.toString();
  // });

  // python.stderr.on('data', function (data) {
  //   console.log(data);
  //   console.log(data.toString());
  //   console.log();
  //   // dataToSend = data.toString();
  // });

  // // in close event we are sure that stream from child process is closed
  // python.on('close', (code) => {
  //   console.log(`child process close all stdio with code ${code}`);
  //   // socket.destroy();
  //   // send data to browser
  // });

  if (isDebug) {
    await installExtensions();
  }

  const RESOURCES_PATH = app.isPackaged
    ? path.join(process.resourcesPath, 'assets')
    : path.join(__dirname, '../../assets');

  const getAssetPath = (...paths: string[]): string => {
    return path.join(RESOURCES_PATH, ...paths);
  };

  mainWindow = new BrowserWindow({
    show: false,
    width: 1024,
    height: 728,
    icon: getAssetPath('icon.png'),
    webPreferences: {
      preload: app.isPackaged
        ? path.join(__dirname, 'preload.js')
        : path.join(__dirname, '../../.erb/dll/preload.js'),
      nodeIntegration: false, // Required for direct IPC communication
      contextIsolation: true, // Required for direct IPC communication
    },
  });

  mainWindow.loadURL(resolveHtmlPath('index.html'));

  mainWindow.on('ready-to-show', () => {
    if (!mainWindow) {
      throw new Error('"mainWindow" is not defined');
    }
    if (process.env.START_MINIMIZED) {
      mainWindow.minimize();
    } else {
      mainWindow.show();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  const menuBuilder = new MenuBuilder(mainWindow);
  menuBuilder.buildMenu();

  // Open urls in the user's browser
  mainWindow.webContents.setWindowOpenHandler((edata) => {
    shell.openExternal(edata.url);
    return { action: 'deny' };
  });

  // Remove this if your app does not use auto updates
  // eslint-disable-next-line
  new AppUpdater();

  io.on('connection', (socket) => {
    console.log('Received a socket connection from the python child');
    const user_id = socket.handshake.headers['user_id'];
    console.log(user_id);

    // Transmit peer_id entered by user (client only) on frontend to the backend
    // IPC.on('has_peer_id' , (peer_id) => {
      // socket.emit('connect_to_peer', data=peer_id)
    // })

    // ipcMain.on('set_peer_id', (event, peer_id) => {
    //     console.log(peer_id);
    // });

    // 'stream' events are accompanied by frame, a bytes object representing an isvm from our python script
    socket.on('stream', (frame) => {
      // Convert bytes to blob
      const frameBlob = new Blob(frame, { type: 'plain/text' });

      // Use promise-based .arrayBuffer() method so we can bypass having a FileReader
      frameBlob
        .arrayBuffer()
        .then((frameBuffer) => {
          const videoFrame = new VideoFrame(frameBuffer);

          // Send this frame to the other window
          win.webContents.send('frame', videoFrame);
        })
        .catch((err) => {
          console.error(err);
        });
    });
  });
};

/**
 * Add event listeners...
 */

app.on('window-all-closed', () => {
  // Respect the OSX convention of having the application in memory even
  // after all windows have been closed
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app
  .whenReady()
  .then(() => {
    ipcMain.on('set_peer_id', (event, peer_id) => {
        console.log(peer_id);
    });

    createWindow();
    app.on('activate', () => {
      // On macOS it's common to re-create a window in the app when the
      // dock icon is clicked and there are no other windows open.
      if (mainWindow === null) createWindow();
    });
  })
  .catch(console.log);
