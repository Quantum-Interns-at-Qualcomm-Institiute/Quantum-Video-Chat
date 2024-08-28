// Disable no-unused-vars, broken for spread args
import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    rendererReady: () => ipcRenderer.send('renderer-ready'),
    joinRoom: (room_id: string) => ipcRenderer.send('join-room', room_id),
    leaveRoom: () => ipcRenderer.send('leave-room'),
    ipcListen: (eventName: string, callback: (event: Electron.IpcRendererEvent, ...args: any[]) => void) => ipcRenderer.on(eventName, callback)
})
