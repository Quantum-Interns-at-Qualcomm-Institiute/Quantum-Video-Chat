/**
 * This module executes inside of electron's main process. You can start
 * electron renderer process from here and communicate with the other processes
 * through IPC.
 *
 * When running `npm run build` or `npm run build:main`, this file is compiled to
 * `./src/main.js` using webpack. This gives us some performance wins.
 */
import path from "node:path";
import * as fs from "node:fs";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { app, BrowserWindow, shell, ipcMain, ipcRenderer } from "electron";
import { autoUpdater } from "electron-updater";
import log from "electron-log";
import MenuBuilder from "./menu";
import { resolveHtmlPath } from "./util";

class AppUpdater {
	constructor() {
		log.transports.file.level = "info";
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
	new AppUpdater();
};

// ---------------------------------------------------------------------------
// Settings INI — read/write helpers (no npm dependency)
// ---------------------------------------------------------------------------

type SettingsData = Record<string, Record<string, string | number | boolean>>;

const SETTINGS_DEFAULTS: SettingsData = {
	network: {
		electron_ipc_port: 5001,
		server_rest_port: 5050,
		server_websocket_port: 3000,
		client_api_port: 4000,
	},
	video: {
		video_width: 640,
		video_height: 480,
		display_width: 960,
		display_height: 720,
		frame_rate: 15,
	},
	audio: {
		sample_rate: 8196,
		audio_wait: 0.125,
		mute_by_default: false,
	},
	encryption: {
		key_length: 128,
		encrypt_scheme: "AES",
		key_generator: "FILE",
	},
	debug: {
		video_enabled: false,
	},
};

// In dev the compiled main.js lives in src/main/ so ../../ reaches project root.
// In production (packaged) adjust via app.getAppPath().
function getSettingsPath(): string {
	return path.join(__dirname, "../../settings.ini");
}

function parseIni(text: string): SettingsData {
	const result: SettingsData = {};
	let currentSection = "";
	for (const raw of text.split("\n")) {
		const line = raw.trim();
		if (!line || line.startsWith("#") || line.startsWith(";")) continue;
		const sectionMatch = line.match(/^\[(.+)]$/);
		if (sectionMatch) {
			currentSection = sectionMatch[1];
			if (!result[currentSection]) result[currentSection] = {};
			continue;
		}
		const eqIdx = line.indexOf("=");
		if (eqIdx > 0 && currentSection) {
			const key = line.slice(0, eqIdx).trim();
			const val = line.slice(eqIdx + 1).trim();
			// Parse booleans, then numbers, then keep as string
			if (val === "true") result[currentSection][key] = true;
			else if (val === "false") result[currentSection][key] = false;
			else {
				const num = Number(val);
				result[currentSection][key] = Number.isNaN(num) ? val : num;
			}
		}
	}
	return result;
}

function stringifyIni(data: SettingsData): string {
	const lines: string[] = [];
	for (const section of Object.keys(data)) {
		lines.push(`[${section}]`);
		for (const [key, val] of Object.entries(data[section])) {
			lines.push(`${key} = ${val}`);
		}
		lines.push("");
	}
	return lines.join("\n");
}

function deepMerge(defaults: SettingsData, overrides: SettingsData): SettingsData {
	const merged: SettingsData = {};
	for (const section of Object.keys(defaults)) {
		merged[section] = { ...defaults[section], ...(overrides[section] || {}) };
	}
	// Include any extra sections from overrides not in defaults
	for (const section of Object.keys(overrides)) {
		if (!merged[section]) merged[section] = { ...overrides[section] };
	}
	return merged;
}

// Register IPC handlers for settings
ipcMain.handle("settings:get", async () => {
	const settingsPath = getSettingsPath();
	if (!fs.existsSync(settingsPath)) return SETTINGS_DEFAULTS;
	try {
		const content = fs.readFileSync(settingsPath, "utf-8");
		return deepMerge(SETTINGS_DEFAULTS, parseIni(content));
	} catch {
		return SETTINGS_DEFAULTS;
	}
});

ipcMain.handle("settings:save", async (_event, settings: SettingsData) => {
	const settingsPath = getSettingsPath();
	fs.writeFileSync(settingsPath, stringifyIni(settings), "utf-8");
	return { ok: true };
});

ipcMain.handle("settings:defaults", async () => {
	return SETTINGS_DEFAULTS;
});

// ---------------------------------------------------------------------------

import http from "node:http";
import { spawn } from "node:child_process";
import { Server, type Socket } from "socket.io";

/**
 * Bind an HTTP server on the lowest available port >= startPort and return
 * both the bound server and the chosen port.
 *
 * Keeping the server open eliminates the TOCTOU race that exists when you
 * probe for a free port and then try to bind it in a separate step.
 */
function bindHttpServer(
	startPort: number,
): Promise<{ httpServer: http.Server; port: number }> {
	return new Promise((resolve, reject) => {
		const httpServer = http.createServer();
		httpServer.listen(startPort, "127.0.0.1", () => {
			const port = (httpServer.address() as import("node:net").AddressInfo).port;
			resolve({ httpServer, port });
		});
		httpServer.on("error", (err: NodeJS.ErrnoException) => {
			if (err.code === "EADDRINUSE") {
				httpServer.close();
				bindHttpServer(startPort + 1).then(resolve).catch(reject);
			} else {
				reject(err);
			}
		});
	});
}

// Python middleware — spawned automatically so running `npm run start:client`
// twice in two terminals is all that is needed for two clients on one machine.
const spawnPythonProcess = async () => {
	// Bind the HTTP server first and keep it open, then attach socket.io to it.
	// This avoids the TOCTOU race where a port is found free but stolen before
	// socket.io gets to bind it.
	const { httpServer, port: ipcPort } = await bindHttpServer(5001);
	// Raw video frames are ~1.2 MB (640×480×4 bytes/pixel).  The default
	// maxHttpBufferSize (1 MB) silently disconnects the client when a frame
	// exceeds the limit, causing reconnection spam.
	const io = new Server(httpServer, { maxHttpBufferSize: 5e6 });

	// Spawn the Python middleware with the chosen IPC port in its environment.
	// QVC_IPC_PORT takes priority over settings.ini inside shared/config.py.
	const projectRoot = path.join(app.getAppPath(), "..");
	const pythonScript = path.join(projectRoot, "middleware", "video_chat.py");
	const python = spawn("python3", [pythonScript], {
		cwd: projectRoot,
		env: { ...process.env, QVC_IPC_PORT: String(ipcPort) },
	});

	python.stdout?.on("data", (data: Buffer) => {
		process.stdout.write(`[middleware] ${data}`);
	});
	python.stderr?.on("data", (data: Buffer) => {
		process.stderr.write(`[middleware] ${data}`);
	});
	python.on("close", (code: number | null) => {
		console.log(`[middleware] Python process exited with code ${code}`);
	});

	// Shut Python down cleanly when Electron quits.
	app.on("before-quit", () => python.kill());

	// Track the latest middleware socket so IPC handlers (registered once)
	// always emit on the most recent connection.
	let middlewareSocket: Socket | null = null;
	let has_peer_id = false;

	// Register the IPC handler ONCE — outside io.on("connection") — so that
	// socket reconnections don't add duplicate listeners to ipcMain.
	ipcMain.on("set_peer_id", (_event, peer_id) => {
		if (has_peer_id) return;
		if (!middlewareSocket) return;
		has_peer_id = true;
		console.log(
			`(main.ts): Received peer_id ${peer_id}; sending to Python subprocess.`,
		);
		middlewareSocket.emit("connect_to_peer", peer_id);
	});

	ipcMain.on("disconnect", () => {
		if (!middlewareSocket) return;
		console.log("(main.ts): Disconnect requested — forwarding to middleware.");
		middlewareSocket.emit("disconnect_call");
		has_peer_id = false;
	});

	ipcMain.on("toggle-mute", () => {
		if (!middlewareSocket) return;
		middlewareSocket.emit("toggle_mute");
	});

	io.on("connection", (socket: Socket) => {
		middlewareSocket = socket;
		socket.emit('successfully_connected', 'Hello world!');

		// 'status' events report connection state changes (server_connecting,
		// server_connected, peer_incoming, peer_outgoing, peer_connected, …).
		socket.on("status", (data: { event: string; data: Record<string, unknown> }) => {
			if (mainWindow !== null) {
				mainWindow.webContents.send("status", data);
				if (data.event === "mute_changed") {
					mainWindow.webContents.send("mute-changed", data.data);
				}
			}
		});

		// 'self-frame' events carry the raw RGBA preview of what this client is sending
		socket.on("self-frame", (data: { frame: Buffer; width: number; height: number }) => {
			if (mainWindow !== null) {
				mainWindow.webContents.send("self-frame", {
					frame: Array.from(data.frame),
					width: data.width,
					height: data.height,
				});
			}
		});

		// 'stream' events carry raw video frame bytes from the peer
		socket.on("stream", (frame: Buffer) => {
			if (mainWindow !== null) {
				mainWindow.webContents.send("frame", Array.from(frame));
			}
		});
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
		// Spawn Python only after the renderer signals it is mounted and its
		// IPC listeners are registered. This prevents status events emitted
		// during connect() from firing into a not-yet-listening window.
		ipcMain.once('renderer-ready', () => {
			spawnPythonProcess();
		});
		createWindow();
		app.on("activate", () => {
			// On macOS it's common to re-create a window in the app when the
			// dock icon is clicked and there are no other windows open.
			if (mainWindow === null) createWindow();
		});
	})
	.catch(console.log);
