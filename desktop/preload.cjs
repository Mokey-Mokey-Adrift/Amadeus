const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("amadeus", {
  command: (action, payload) => ipcRenderer.invoke("amadeus:command", action, payload),
  onEvent: (listener) => {
    const handler = (_event, message) => listener(message);
    ipcRenderer.on("amadeus:event", handler);
    return () => ipcRenderer.removeListener("amadeus:event", handler);
  },
});
