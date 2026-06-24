import { app, BrowserWindow, dialog, ipcMain } from 'electron';
import * as path from 'path';
import log from 'electron-log';
import { BackendManager } from './services/backend-manager';
import { UpdaterService } from './services/updater';
import { TrayManager } from './services/tray';

// Configure logging
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

let mainWindow: BrowserWindow | null = null;
let backendManager: BackendManager;
let updater: UpdaterService;
let trayManager: TrayManager;
let isQuitting = false;

function createWindow(): void {
  log.info('Creating main window...');

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'AI知识库管理系统',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    },
    show: false
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    if (mainWindow) {
      mainWindow.show();
      log.info('Main window shown');
    }
  });

  // Handle window close
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      handleWindowClose();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Load frontend
  loadFrontend();
}

function loadFrontend(): void {
  if (!mainWindow) return;

  if (app.isPackaged) {
    // In production, load from file or local server
    // For now, we'll load the Next.js standalone build
    // This would typically be served by a local HTTP server
    const frontendPath = path.join(process.resourcesPath, 'frontend');
    const indexPath = path.join(frontendPath, 'server.js');

    // You might want to start a local server here or load static files
    // For now, show a loading message
    mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <title>AI知识库管理系统</title>
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
              display: flex;
              justify-content: center;
              align-items: center;
              height: 100vh;
              margin: 0;
              background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
              color: white;
            }
            .container {
              text-align: center;
            }
            h1 { margin-bottom: 20px; }
            p { opacity: 0.9; }
          </style>
        </head>
        <body>
          <div class="container">
            <h1>🚀 AI知识库管理系统</h1>
            <p>正在启动后端服务...</p>
          </div>
        </body>
      </html>
    `));

    log.info('Frontend loaded (production mode)');
  } else {
    // In development, load from dev server
    const devServerUrl = 'http://localhost:3000';
    mainWindow.loadURL(devServerUrl);
    log.info(`Loading from dev server: ${devServerUrl}`);

    // Open DevTools in development
    mainWindow.webContents.openDevTools();
  }
}

async function handleWindowClose(): Promise<void> {
  if (!mainWindow) return;

  const { response } = await dialog.showMessageBox(mainWindow, {
    type: 'question',
    buttons: ['最小化到托盘', '退出', '取消'],
    defaultId: 0,
    cancelId: 2,
    title: '确认操作',
    message: '您想要最小化到系统托盘还是退出程序？'
  });

  if (response === 0) {
    // Minimize to tray
    mainWindow.hide();
    log.info('Window minimized to tray');
  } else if (response === 1) {
    // Quit
    app.quit();
  }
  // response === 2: Cancel, do nothing
}

function setupIPC(): void {
  // Get backend URL
  ipcMain.handle('get-backend-url', () => {
    return backendManager.getUrl();
  });

  // Check for updates
  ipcMain.handle('check-updates', async () => {
    await updater.checkNow();
    return { success: true };
  });

  // Get app version
  ipcMain.handle('get-app-version', () => {
    return app.getVersion();
  });
}

async function initializeApp(): Promise<void> {
  log.info('Initializing application...');

  // Create backend manager
  backendManager = new BackendManager();

  // Set up backend event handlers
  backendManager.on('ready', () => {
    log.info('Backend is ready, updating frontend');
    if (mainWindow) {
      // Notify frontend that backend is ready
      mainWindow.webContents.send('backend-ready', backendManager.getUrl());
    }
  });

  backendManager.on('error', (error) => {
    log.error('Backend error:', error);
    if (mainWindow) {
      dialog.showMessageBox(mainWindow, {
        type: 'error',
        title: '后端服务错误',
        message: `后端服务发生错误: ${error.message}`,
        buttons: ['确定']
      });
    }
  });

  backendManager.on('exit', (code) => {
    log.warn(`Backend exited with code ${code}`);
  });

  // Start backend
  try {
    await backendManager.start();
    log.info(`Backend started on ${backendManager.getUrl()}`);
  } catch (error) {
    log.error('Failed to start backend:', error);
  }

  // Create updater service
  updater = new UpdaterService();
  if (mainWindow) {
    updater.init(mainWindow);
  }

  // Create tray manager
  trayManager = new TrayManager();
  if (mainWindow) {
    trayManager.init(mainWindow, () => updater.checkNow());
  }
}

// App lifecycle
app.whenReady().then(async () => {
  log.info('App ready');

  createWindow();
  setupIPC();
  await initializeApp();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', async (event) => {
  if (!isQuitting) {
    event.preventDefault();
    isQuitting = true;

    log.info('Quitting application...');

    // Stop backend
    if (backendManager) {
      try {
        await backendManager.stop();
      } catch (error) {
        log.error('Error stopping backend:', error);
      }
    }

    // Destroy updater
    if (updater) {
      updater.destroy();
    }

    // Destroy tray
    if (trayManager) {
      trayManager.destroy();
    }

    // Close all windows
    BrowserWindow.getAllWindows().forEach((win) => {
      win.removeAllListeners('close');
      win.close();
    });

    app.exit(0);
  }
});

app.on('quit', () => {
  log.info('Application quit');
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  log.error('Uncaught exception:', error);
});

process.on('unhandledRejection', (reason) => {
  log.error('Unhandled rejection:', reason);
});
