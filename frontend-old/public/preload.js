const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
    startHost: () => ipcRenderer.invoke('session:host'),
    startClient: () => ipcRenderer.invoke('session:client'),
    onSelfFrame: () => ipcRenderer.on('frame:self', callback),
    onPeerFrame: () => ipcRenderer.on('frame:peer', callback)
})