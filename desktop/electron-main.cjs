const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("node:child_process");
const readline = require("node:readline");
const fs = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const MESSAGE_PREFIX = "@@AMADEUS@@";
const pendingRequests = new Map();
let backendProcess;
let mainWindow;

function sendEvent(event) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("amadeus:event", event);
  }
}

function failPendingRequests(message) {
  for (const [, request] of pendingRequests) {
    clearTimeout(request.timeout);
    request.reject(new Error(message));
  }
  pendingRequests.clear();
}

function startBackend() {
  const configuredPython = process.env.AMADEUS_PYTHON;
  const virtualEnvPython = process.platform === "win32"
    ? path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
    : path.join(PROJECT_ROOT, "venv", "bin", "python");
  const python = configuredPython || (
    fs.existsSync(virtualEnvPython)
      ? virtualEnvPython
      : (process.platform === "win32" ? "python" : "python3")
  );
  const backendScript = path.join(PROJECT_ROOT, "desktop", "backend_server.py");

  backendProcess = spawn(python, [backendScript], {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
    },
    stdio: ["pipe", "pipe", "pipe"],
    windowsHide: true,
  });

  const stdout = readline.createInterface({ input: backendProcess.stdout });
  stdout.on("line", (line) => {
    if (!line.startsWith(MESSAGE_PREFIX)) {
      if (line.trim()) console.log(`[Python] ${line}`);
      return;
    }

    try {
      const message = JSON.parse(line.slice(MESSAGE_PREFIX.length));
      if (message.type === "response") {
        const pending = pendingRequests.get(message.request_id);
        if (!pending) return;
        clearTimeout(pending.timeout);
        pendingRequests.delete(message.request_id);
        if (message.ok) pending.resolve(message.result);
        else pending.reject(new Error(message.error));
      } else if (message.type === "event") {
        sendEvent(message);
      }
    } catch (error) {
      console.error("Invalid response from Python backend:", error);
      sendEvent({
        type: "event",
        event: "error",
        message: "Не удалось прочитать ответ Python-сервера.",
      });
    }
  });

  backendProcess.stderr.on("data", (chunk) => {
    console.error(`[Python] ${chunk.toString().trimEnd()}`);
  });

  backendProcess.on("error", (error) => {
    failPendingRequests(`Не удалось запустить Python: ${error.message}`);
    sendEvent({
      type: "event",
      event: "error",
      message: `Не удалось запустить Python: ${error.message}`,
    });
  });

  backendProcess.on("exit", (code, signal) => {
    backendProcess = undefined;
    failPendingRequests(
      `Python-сервер завершился (${signal || `код ${code ?? "неизвестен"}`}).`,
    );
    if (code !== 0 && code !== null) {
      sendEvent({
        type: "event",
        event: "error",
        message: `Python-сервер завершился с кодом ${code}.`,
      });
    }
  });
}

function sendCommand(action, payload = {}) {
  if (!backendProcess || backendProcess.killed || !backendProcess.stdin.writable) {
    return Promise.reject(new Error("Python-сервер ещё не запущен."));
  }

  const requestId = randomUUID();
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(new Error("Python-сервер не ответил вовремя."));
    }, 30_000);
    pendingRequests.set(requestId, { resolve, reject, timeout });
    backendProcess.stdin.write(
      `${JSON.stringify({ request_id: requestId, action, payload })}\n`,
      (error) => {
        if (!error) return;
        clearTimeout(timeout);
        pendingRequests.delete(requestId);
        reject(error);
      },
    );
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1160,
    height: 780,
    minWidth: 760,
    minHeight: 560,
    backgroundColor: "#111114",
    title: "Amadeus",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const devServerUrl = process.env.AMADEUS_DEV_SERVER_URL;
  if (devServerUrl) {
    mainWindow.loadURL(devServerUrl);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(PROJECT_ROOT, "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = undefined;
  });
}

function stopBackend() {
  if (!backendProcess) return;
  backendProcess.stdin.end();
  const child = backendProcess;
  const timeout = setTimeout(() => {
    if (child && !child.killed) child.kill();
  }, 2_000);
  child.once("exit", () => clearTimeout(timeout));
}

ipcMain.handle("amadeus:command", (_event, action, payload) => (
  sendCommand(action, payload)
));

app.whenReady().then(() => {
  startBackend();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("before-quit", stopBackend);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
