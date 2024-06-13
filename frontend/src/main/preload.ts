// Disable no-unused-vars, broken for spread args
import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    rendererReady: () => ipcRenderer.send('renderer-ready'),
    joinPeer: (peer_id: string) => ipcRenderer.send('set_peer_id', peer_id),
    ipcListen: (eventName: string, callback: (event: Electron.IpcRendererEvent, ...args: any[]) => void) => ipcRenderer.on(eventName, callback)
})
