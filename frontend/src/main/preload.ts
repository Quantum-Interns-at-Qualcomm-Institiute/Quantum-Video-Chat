// Disable no-unused-vars, broken for spread args
import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    rendererReady: () => ipcRenderer.send('renderer-ready'),
    joinRoom: async (room_id: string) => await ipcRenderer.invoke('join-room', room_id),
    leaveRoom: async () => await ipcRenderer.invoke('leave-room'),
    ipcListen: (eventName: string, callback: (event: Electron.IpcRendererEvent, ...args: any[]) => void) => ipcRenderer.on(eventName, callback),
    ipcRemoveListener: (eventName: string) => ipcRenderer.removeAllListeners(eventName)
})
