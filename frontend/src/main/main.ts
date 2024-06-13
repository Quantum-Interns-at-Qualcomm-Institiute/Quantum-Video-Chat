/**
 * This module executes inside of electron's main process. You can start
 * electron renderer process from here and communicate with the other processes
 * through IPC.
 *
 * When running `npm run build` or `npm run build:main`, this file is compiled to
 * `./src/main.js` using webpack. This gives us some performance wins.
 */
import path from "node:path";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { app, BrowserWindow, shell, ipcMain, ipcRenderer } from "electron";
import { autoUpdater } from "electron-updater";
import log from "electron-log";
import MenuBuilder from "./menu";
import { resolveHtmlPath } from "./util";
import { Server, type Socket } from "socket.io";

const DEFAULT_FRONTEND_PORT = 5001;

class AppUpdater {
	constructor() {
		log.transports.file.level = "info";
		autoUpdater.logger = log;
		autoUpdater.checkForUpdatesAndNotify();
	}
}

let mainWindow: BrowserWindow | null = null;

if (process.env.NODE_ENV === "production") {
	const sourceMapSupport = require("source-map-support");
	sourceMapSupport.install();
}

// const isDebug =
// process.env.NODE_ENV === 'development' || process.env.DEBUG_PROD === 'true';

const isDebug = false;

if (isDebug) {
	require("electron-debug")();
}

const installExtensions = async () => {
	const installer = require("electron-devtools-installer");
	const forceDownload = !!process.env.UPGRADE_EXTENSIONS;
	const extensions = ["REACT_DEVELOPER_TOOLS"];

	return installer
		.default(
			extensions.map((name) => installer[name]),
			forceDownload,
		)
		.catch(console.log);
};

const createWindow = async () => {
	if (isDebug) {
		await installExtensions();
	}

	const RESOURCES_PATH = app.isPackaged
		? path.join(process.resourcesPath, "assets")
		: path.join(__dirname, "../../assets");

	const getAssetPath = (...paths: string[]): string => {
		return path.join(RESOURCES_PATH, ...paths);
	};

	mainWindow = new BrowserWindow({
		show: false,
		width: 1024,
		height: 728,
		icon: getAssetPath("icon.png"),
		webPreferences: {
			preload: app.isPackaged
				? path.join(__dirname, "preload.js")
				: path.join(__dirname, "../../.erb/dll/preload.js"),
			nodeIntegration: false, // Required for direct IPC communication
			contextIsolation: true, // Required for direct IPC communication
		},
	});

	mainWindow.loadURL(resolveHtmlPath("index.html"));

	mainWindow.on("ready-to-show", () => {
		if (!mainWindow) {
			throw new Error('"mainWindow" is not defined');
		}
		if (process.env.START_MINIMIZED) {
			mainWindow.minimize();
		} else {
			mainWindow.show();
		}
	});

	mainWindow.on("closed", () => {
		mainWindow = null;
	});

	const menuBuilder = new MenuBuilder(mainWindow);
	menuBuilder.buildMenu();

	// Open urls in the user's browser
	mainWindow.webContents.setWindowOpenHandler((edata) => {
		shell.openExternal(edata.url);
		return { action: "deny" };
	});

	// Remove this if your app does not use auto updates
	// eslint-disable-next-line
	// new AppUpdater();
};

/**
 * Start socket.io server to communicate with Python subprocess
 * Set up event listeners to send events from Python to React, vice-versa
 * @param {number} PORT Default port to listen on.
 * 						Will iteratively increment port if default is in use
 * @return {number} 	Port socket is bound to, for Python subprocess to connect to
 */
const listenForSocketAndIPC = (PORT: number) => {
	let io = new Server(PORT, {
		maxHttpBufferSize: 1e7
	});
	console.log(`(main.ts): Starting frontend socket on port ${PORT}`);
	process.on('uncaughtException', function(err) {
		if(err.code !== 'EADDRINUSE') throw err;
		console.log(`(main.ts): Port ${PORT} in use; re-trying with port ${PORT+1}`)
		io = new Server(++PORT);
	});


	io.on("connection", (socket: Socket) => {
		console.log("(main.ts): Received connection from Python subproccess");
		const user_id = socket.handshake.headers.user_id;
		ipcMain.once("set_peer_id", (event, peer_id) => {
			// bodgey way of ignoring extraneous requests due to additional runs of useEffect in Session.tsx
			console.log(
				`(main.ts): Received peer_id ${peer_id} from renderer; sending to Python subprocess.`,
			);
			socket.emit("connect_to_peer", peer_id);
		});

		socket.on('self_id', (self_id) => {
			console.log(`(main.ts): Received self_id ${self_id} from python subprocess; sending to renderer.`)
			mainWindow?.webContents.send('self_id', self_id);
		});

		// 'stream' events are accompanied by frame, a bytes object representing an isvm from our python script
		socket.on("stream", (data) => {
			console.log(`Passing frame #${data.count} of size ${data.width}x${data.height} from backend to renderer`)

			try {
				// Send this frame to the other window
				if (mainWindow !== null) {
					mainWindow.webContents.send("frame", data);
				} else throw new Error("main window is null");
			} catch (error) {
				console.log(`Error: ${error}`)
			}

		});
	});

	return PORT;
}

// Spawn the Python 
const spawnPythonProcess = (PORT: number) => {
	console.log("(main.ts): Spawning Python Child Process...");
	const { spawn } = require("node:child_process");
	// TODO: Find elegant solution to figure out the name of user's python executable
	// Sometimes it's 'python'; sometimes it's 'python3'; sometimes it's 'py'
	const python = spawn("py", ['-u', 'src/middleware/main.py', [PORT]]);

	// In close event we are sure that stream from child process is closed
	python.on("close", (code: string | null) => {
		console.log(`(py): Child process closed with code ${code}.`);
		// send data to browser
	});


	// trim() removes newlines automatically included the python outputs
	python.stdout.setEncoding('utf8');
	python.stdout.on('data', (data: string) => {
    	console.log(`(py stdout): ${data.trim()}`);
	});

	python.stderr.setEncoding('utf8');
	python.stderr.on('data', (data: string) => {
		console.log(`(py stderr): ${data.trim()}`);
	});
};

/**
 * Add event listeners...
 */

app.on("window-all-closed", () => {
	// Respect the OSX convention of having the application in memory even
	// after all windows have been closed
	if (process.platform !== "darwin") {
		app.quit();
	}
});

app
	.whenReady()
	.then(() => {
		const FRONTEND_PORT = listenForSocketAndIPC(DEFAULT_FRONTEND_PORT);
		spawnPythonProcess(FRONTEND_PORT);
		createWindow();
		app.on("activate", () => {
			// On macOS it's common to re-create a window in the app when the
			// dock icon is clicked and there are no other windows open.
			if (mainWindow === null) createWindow();
		});
	})
	.catch(console.log);
