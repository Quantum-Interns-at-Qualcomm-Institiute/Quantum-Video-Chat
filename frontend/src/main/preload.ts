// Disable no-unused-vars, broken for spread args
import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    rendererReady: () => ipcRenderer.send('renderer-ready'),
    joinPeer: (peer_id: string) => ipcRenderer.send('set-peer-id', peer_id),
    quitSession: () => ipcRenderer.send('quit-session'),
    ipcListen: (eventName: string, callback: (event: Electron.IpcRendererEvent, ...args: any[]) => void) => ipcRenderer.on(eventName, callback)
})
