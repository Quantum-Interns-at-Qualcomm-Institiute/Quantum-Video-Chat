import { app, BrowserWindow } from 'electron';
import * as path from 'path';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'QVC Server Dashboard',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // In development, load from the Vite dev server.
  // In production, load the built index.html.
  const isDev = !app.isPackaged;
  if (isDev) {
    const port = process.env.VITE_PORT || '5173';
    mainWindow.loadURL(`http://localhost:${port}`);
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});
