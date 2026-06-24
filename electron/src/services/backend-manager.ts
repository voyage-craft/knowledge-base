import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs';
import * as http from 'http';
import * as crypto from 'crypto';
import { app } from 'electron';
import log from 'electron-log';

export class BackendManager extends EventEmitter {
  private process: ChildProcess | null = null;
  private port: number = 8000;
  private ready: boolean = false;
  private healthCheckFailures: number = 0;
  private maxHealthCheckFailures: number = 3;
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private backendPath: string;
  private pythonPath: string;

  constructor() {
    super();
    this.backendPath = this.getBackendPath();
    this.pythonPath = '';
  }

  private getBackendPath(): string {
    if (app.isPackaged) {
      return path.join(process.resourcesPath, 'backend');
    } else {
      return path.join(__dirname, '..', '..', '..', 'backend');
    }
  }

  private getEmbeddedPythonPath(): string {
    if (app.isPackaged) {
      if (process.platform === 'win32') {
        return path.join(process.resourcesPath, 'backend', 'python.exe');
      } else {
        return path.join(process.resourcesPath, 'backend', 'python');
      }
    }
    return '';
  }

  private async detectPython(): Promise<string> {
    // Try embedded Python first (for packaged app)
    const embeddedPython = this.getEmbeddedPythonPath();
    if (embeddedPython && fs.existsSync(embeddedPython)) {
      log.info('Using embedded Python:', embeddedPython);
      return embeddedPython;
    }

    // Try system Python
    const pythonCommands = process.platform === 'win32'
      ? ['python', 'python3']
      : ['python3', 'python'];

    for (const cmd of pythonCommands) {
      try {
        const version = await this.checkPythonVersion(cmd);
        if (version) {
          log.info(`Found Python: ${cmd} (${version})`);
          return cmd;
        }
      } catch (error) {
        // Continue to next command
      }
    }

    throw new Error('Python not found. Please install Python 3.8 or later.');
  }

  private checkPythonVersion(cmd: string): Promise<string | null> {
    return new Promise((resolve) => {
      const proc = spawn(cmd, ['--version']);
      let output = '';

      proc.stdout.on('data', (data) => {
        output += data.toString();
      });

      proc.stderr.on('data', (data) => {
        output += data.toString();
      });

      proc.on('close', (code) => {
        if (code === 0 && output.includes('Python 3')) {
          resolve(output.trim());
        } else {
          resolve(null);
        }
      });

      proc.on('error', () => {
        resolve(null);
      });
    });
  }

  private ensureEnvFile(): void {
    const envPath = path.join(this.backendPath, '.env');

    if (!fs.existsSync(envPath)) {
      log.info('Creating default .env file');
      const jwtSecret = crypto.randomBytes(32).toString('hex');
      const defaultEnv = `# AI Knowledge Base Backend Configuration
DATABASE_URL=sqlite:///./knowledge_base.db
JWT_SECRET_KEY=${jwtSecret}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=http://localhost:3000
DEBUG=false
`;
      fs.writeFileSync(envPath, defaultEnv, 'utf-8');
      log.info('Default .env file created at:', envPath);
    }
  }

  private async findAvailablePort(startPort: number = 8000): Promise<number> {
    return new Promise((resolve) => {
      const server = http.createServer();
      server.listen(startPort, '127.0.0.1', () => {
        const port = (server.address() as any).port;
        server.close(() => resolve(port));
      });
      server.on('error', () => {
        resolve(this.findAvailablePort(startPort + 1));
      });
    });
  }

  async start(): Promise<void> {
    try {
      log.info('Starting backend manager...');

      // Detect Python
      this.pythonPath = await this.detectPython();

      // Ensure .env exists
      this.ensureEnvFile();

      // Find available port
      this.port = await this.findAvailablePort(8000);
      log.info(`Using port: ${this.port}`);

      // Start uvicorn
      await this.startUvicorn();

      // Start health check
      this.startHealthCheck();
    } catch (error) {
      log.error('Failed to start backend:', error);
      this.emit('error', error);
      throw error;
    }
  }

  private startUvicorn(): Promise<void> {
    return new Promise((resolve, reject) => {
      const args = [
        '-m', 'uvicorn',
        'app.main:app',
        '--host', '127.0.0.1',
        '--port', String(this.port)
      ];

      log.info(`Starting uvicorn: ${this.pythonPath} ${args.join(' ')}`);

      this.process = spawn(this.pythonPath, args, {
        cwd: this.backendPath,
        env: { ...process.env },
        stdio: ['ignore', 'pipe', 'pipe']
      });

      let startupComplete = false;

      this.process.stdout?.on('data', (data) => {
        const output = data.toString();
        log.info(`[Backend stdout] ${output.trim()}`);

        if (output.includes('Application startup complete')) {
          startupComplete = true;
          log.info('Backend startup complete');
          resolve();
        }
      });

      this.process.stderr?.on('data', (data) => {
        const output = data.toString();
        log.error(`[Backend stderr] ${output.trim()}`);
      });

      this.process.on('error', (error) => {
        log.error('Backend process error:', error);
        this.emit('error', error);
        if (!startupComplete) {
          reject(error);
        }
      });

      this.process.on('exit', (code, signal) => {
        log.info(`Backend process exited with code ${code}, signal ${signal}`);
        this.ready = false;
        this.emit('exit', code, signal);

        if (!startupComplete) {
          reject(new Error(`Backend exited with code ${code}`));
        }
      });

      // Timeout after 30 seconds
      setTimeout(() => {
        if (!startupComplete) {
          reject(new Error('Backend startup timeout'));
        }
      }, 30000);
    });
  }

  private startHealthCheck(): void {
    this.healthCheckInterval = setInterval(async () => {
      const healthy = await this.checkHealth();

      if (healthy) {
        this.healthCheckFailures = 0;
        if (!this.ready) {
          this.ready = true;
          log.info('Backend is ready');
          this.emit('ready');
        }
      } else {
        this.healthCheckFailures++;
        log.warn(`Health check failed (${this.healthCheckFailures}/${this.maxHealthCheckFailures})`);

        if (this.healthCheckFailures >= this.maxHealthCheckFailures) {
          log.error('Backend unhealthy, attempting restart');
          await this.restart();
        }
      }
    }, 5000);
  }

  private checkHealth(): Promise<boolean> {
    return new Promise((resolve) => {
      const req = http.get(`http://127.0.0.1:${this.port}/api/health`, (res) => {
        resolve(res.statusCode === 200);
      });

      req.on('error', () => {
        resolve(false);
      });

      req.setTimeout(2000, () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  private async restart(): Promise<void> {
    log.info('Restarting backend...');
    await this.stop();
    this.healthCheckFailures = 0;
    await this.start();
  }

  async stop(): Promise<void> {
    log.info('Stopping backend...');

    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }

    if (this.process) {
      return new Promise((resolve) => {
        const proc = this.process!;

        const forceKillTimeout = setTimeout(() => {
          log.warn('Force killing backend process');
          proc.kill('SIGKILL');
        }, 5000);

        proc.on('exit', () => {
          clearTimeout(forceKillTimeout);
          this.process = null;
          this.ready = false;
          log.info('Backend stopped');
          resolve();
        });

        log.info('Sending SIGTERM to backend');
        proc.kill('SIGTERM');
      });
    }

    resolve();
  }

  getPort(): number {
    return this.port;
  }

  isReady(): boolean {
    return this.ready;
  }

  getUrl(): string {
    return `http://127.0.0.1:${this.port}`;
  }
}
