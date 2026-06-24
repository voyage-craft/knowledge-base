import { Tray, Menu, nativeImage, BrowserWindow, app } from 'electron';
import * as path from 'path';
import log from 'electron-log';

export class TrayManager {
  private tray: Tray | null = null;
  private mainWindow: BrowserWindow | null = null;
  private onCheckUpdates: (() => void) | null = null;

  init(mainWindow: BrowserWindow, onCheckUpdates: () => void): void {
    this.mainWindow = mainWindow;
    this.onCheckUpdates = onCheckUpdates;

    this.createTray();
  }

  private getIconPath(): string {
    const resourcesPath = app.isPackaged
      ? process.resourcesPath
      : path.join(__dirname, '..', '..', 'resources');

    if (process.platform === 'win32') {
      return path.join(resourcesPath, 'icon.ico');
    } else if (process.platform === 'darwin') {
      return path.join(resourcesPath, 'icon.icns');
    } else {
      return path.join(resourcesPath, 'icon.png');
    }
  }

  private createTray(): void {
    try {
      const iconPath = this.getIconPath();
      let trayIcon: nativeImage;

      // Try to load icon, fallback to empty icon if not found
      try {
        trayIcon = nativeImage.createFromPath(iconPath);
        if (trayIcon.isEmpty()) {
          throw new Error('Icon is empty');
        }
      } catch (error) {
        log.warn('Failed to load tray icon, using default:', error);
        trayIcon = nativeImage.createEmpty();
      }

      // Resize for tray (16x16 on Windows, 22x22 on macOS)
      if (!trayIcon.isEmpty()) {
        trayIcon = trayIcon.resize({ width: 16, height: 16 });
      }

      this.tray = new Tray(trayIcon);
      this.tray.setToolTip('AI知识库管理系统');

      this.updateContextMenu();

      // Double-click to show window
      this.tray.on('double-click', () => {
        this.showWindow();
      });

      log.info('System tray created');
    } catch (error) {
      log.error('Failed to create system tray:', error);
    }
  }

  private updateContextMenu(): void {
    if (!this.tray) return;

    const contextMenu = Menu.buildFromTemplate([
      {
        label: '显示主窗口',
        click: () => {
          this.showWindow();
        }
      },
      {
        label: '检查更新...',
        click: () => {
          if (this.onCheckUpdates) {
            this.onCheckUpdates();
          }
        }
      },
      { type: 'separator' },
      {
        label: '退出',
        click: () => {
          app.quit();
        }
      }
    ]);

    this.tray.setContextMenu(contextMenu);
  }

  private showWindow(): void {
    if (this.mainWindow) {
      if (this.mainWindow.isMinimized()) {
        this.mainWindow.restore();
      }
      this.mainWindow.show();
      this.mainWindow.focus();
    }
  }

  destroy(): void {
    if (this.tray) {
      this.tray.destroy();
      this.tray = null;
    }
  }
}
