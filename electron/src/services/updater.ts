import { autoUpdater, UpdateInfo } from 'electron-updater';
import { BrowserWindow } from 'electron';
import log from 'electron-log';

export class UpdaterService {
  private mainWindow: BrowserWindow | null = null;
  private checkInterval: NodeJS.Timeout | null = null;
  private updateAvailable: UpdateInfo | null = null;

  init(mainWindow: BrowserWindow): void {
    this.mainWindow = mainWindow;

    // Configure autoUpdater
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = true;

    // Set up logging
    autoUpdater.logger = log;
    log.info('Updater service initialized');

    // Event handlers
    autoUpdater.on('checking-for-update', () => {
      log.info('Checking for updates...');
    });

    autoUpdater.on('update-available', (info: UpdateInfo) => {
      log.info('Update available:', info.version);
      this.updateAvailable = info;

      if (this.mainWindow) {
        this.mainWindow.webContents.send('update-available', {
          version: info.version,
          releaseDate: info.releaseDate,
          releaseNotes: info.releaseNotes
        });
      }
    });

    autoUpdater.on('update-not-available', () => {
      log.info('No updates available');
      this.updateAvailable = null;
    });

    autoUpdater.on('download-progress', (progress) => {
      log.info(`Download progress: ${progress.percent.toFixed(1)}%`);
    });

    autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
      log.info('Update downloaded:', info.version);

      if (this.mainWindow) {
        this.mainWindow.webContents.send('update-downloaded', {
          version: info.version,
          releaseDate: info.releaseDate,
          releaseNotes: info.releaseNotes
        });
      }
    });

    autoUpdater.on('error', (error) => {
      log.error('Updater error:', error);
    });

    // Check for updates on startup
    this.checkForUpdates();

    // Check for updates every 4 hours
    this.checkInterval = setInterval(() => {
      this.checkForUpdates();
    }, 4 * 60 * 60 * 1000);
  }

  async checkForUpdates(): Promise<void> {
    try {
      await autoUpdater.checkForUpdates();
    } catch (error) {
      log.error('Failed to check for updates:', error);
    }
  }

  async checkNow(): Promise<void> {
    log.info('Manual update check triggered');
    await this.checkForUpdates();
  }

  async downloadAndInstall(): Promise<void> {
    if (!this.updateAvailable) {
      log.warn('No update available to download');
      return;
    }

    try {
      log.info('Downloading and installing update...');
      await autoUpdater.downloadUpdate();
    } catch (error) {
      log.error('Failed to download update:', error);
      throw error;
    }
  }

  quitAndInstall(): void {
    log.info('Quitting and installing update...');
    autoUpdater.quitAndInstall();
  }

  destroy(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }
}
