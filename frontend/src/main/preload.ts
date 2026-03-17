// Disable no-unused-vars, broken for spread args
import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    setPeerId: (peer_id: string) => ipcRenderer.send('set_peer_id', peer_id),
    ipcListen: (eventName: string, callback: (event: Electron.IpcRendererEvent, ...args: any[]) => void) => ipcRenderer.on(eventName, callback),
    ipcRemoveListener: (eventName: string) => ipcRenderer.removeAllListeners(eventName),
    rendererReady: () => ipcRenderer.send('renderer-ready'),
    disconnect: () => ipcRenderer.send('disconnect'),
    toggleMute: () => ipcRenderer.send('toggle-mute'),

    // Settings IPC
    getSettings: () => ipcRenderer.invoke('settings:get'),
    saveSettings: (settings: Record<string, Record<string, string | number>>) => ipcRenderer.invoke('settings:save', settings),
    getDefaults: () => ipcRenderer.invoke('settings:defaults'),
})
