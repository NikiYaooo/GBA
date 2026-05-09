import { app, BrowserWindow, ipcMain, shell, dialog } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import { spawn, execSync, ChildProcess } from 'node:child_process'
import net from 'node:net'

// The built directory structure
//
// ├─┬─┬ dist
// │ │ └── index.html
// │ │
// │ ├─┬ dist-electron
// │ │ ├── main.js
// │ │ └── preload.js
// │
process.env.DIST = path.join(__dirname, '../dist')
process.env.VITE_PUBLIC = app.isPackaged ? process.env.DIST : path.join(process.env.DIST, '../public')


let win: BrowserWindow | null
let pythonProcess: ChildProcess | null = null
let backendBaseUrl = 'http://127.0.0.1:8000'

/**
 * 在指定端口范围内挑选一个可用端口。
 */
async function pickAvailablePort(startPort: number, endPort: number): Promise<number> {
  const tryPort = (port: number) => new Promise<boolean>((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => {
      server.close(() => resolve(true))
    })
    server.listen(port, '127.0.0.1')
  })

  for (let port = startPort; port <= endPort; port += 1) {
    // eslint-disable-next-line no-await-in-loop
    const ok = await tryPort(port)
    if (ok) return port
  }
  return startPort
}

// 启动 Python 后端
/**
 * 强制清理所有残留的 Python 进程（防止旧版后端占用端口）
 */
function killExistingPythonProcesses() {
  try {
    execSync('taskkill /f /im python.exe 2>nul', { stdio: 'ignore' })
  } catch {
    // ignore
  }
}

/**
 * 启动 Python 后端。若 8000 端口被占用，会自动选择 8001-8010。
 */
async function startPythonBackend() {
  // 杀掉占用 8000 端口的旧 Python 进程（防止旧版本后端干扰）
  try {
    execSync(
      'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :8000 ^| findstr LISTENING\') do taskkill /f /pid %a 2>nul',
      { stdio: 'ignore', shell: 'cmd.exe', timeout: 3000 }
    )
  } catch { /* ignore */ }
  // 在打包环境下，如果当前系统没有安装 Python，或者没有安装相应的依赖，直接调用 python 会失败。
  // 为了确保后端稳定运行，我们可以指定尝试使用自带的环境，或者捕获并展示具体的报错。
  let pythonExecutable = 'python' 

  // 如果根目录下有 .venv 环境，优先使用它（提升在开发机器上测试打包产物的成功率）
  const fsLocal = require('node:fs')
  const possibleVenvPaths = [
    path.join(process.cwd(), '.venv', 'Scripts', 'python.exe'),
    path.join(process.cwd(), '..', '.venv', 'Scripts', 'python.exe'), // 从 release2/xxx.exe 启动时
    path.join(app.getAppPath(), '..', '..', '.venv', 'Scripts', 'python.exe'),
    'E:\\game_builder\\.venv\\Scripts\\python.exe' // 针对当前开发机器的绝对保底路径
  ]

  for (const p of possibleVenvPaths) {
    if (fsLocal.existsSync(p)) {
      pythonExecutable = p
      break
    }
  }

  // 在开发环境中，api 目录在项目根目录
  // 在打包后，api 目录在 resources 目录下
  const scriptPath = app.isPackaged 
    ? path.join(process.resourcesPath, 'api/main.py')
    : path.join(process.cwd(), 'api/main.py')

  const portableDir = process.env.PORTABLE_EXECUTABLE_DIR
  const candidateBaseDirs = app.isPackaged
    ? [portableDir, path.dirname(app.getPath('exe')), app.getPath('userData')].filter(Boolean) as string[]
    : [process.cwd()]

  // 优先复用已有的 data 目录（跨版本持久化，避免每次切换版本丢失知识库数据）
  let dataDir = ''

  // 检查固定位置的启动配置（launcher-config.json）中是否指定了数据目录
  const appDataDir = path.join(process.env.APPDATA || path.join(require('node:os').homedir(), 'AppData', 'Roaming'), 'GameBuilderAIHelper')
  const launcherConfigPath = path.join(appDataDir, 'launcher-config.json')
  try {
    if (fs.existsSync(launcherConfigPath)) {
      const lc = JSON.parse(fs.readFileSync(launcherConfigPath, 'utf-8'))
      if (lc.dataPath && typeof lc.dataPath === 'string' && lc.dataPath.trim()) {
        const customDir = lc.dataPath.trim()
        fs.mkdirSync(customDir, { recursive: true })
        dataDir = customDir
      }
    }
  } catch { /* ignore launcher config errors */ }

  if (!dataDir) {
  const searchDirs = [...candidateBaseDirs]
  // 也检查 portableDir 的父目录下其他 release 文件夹
  if (portableDir) {
    const parentDir = path.dirname(portableDir)
    try {
      const entries = fs.readdirSync(parentDir, { withFileTypes: true })
      for (const entry of entries.reverse()) {
        if (entry.isDirectory() && entry.name !== path.basename(portableDir)) {
          searchDirs.push(path.join(parentDir, entry.name))
        }
      }
    } catch { /* ignore */ }
  }

  for (const base of searchDirs) {
    const candidate = path.join(base, 'data')
    const kbDir = path.join(candidate, 'kb')
    try {
      // 优先使用已有知识库数据的目录
      if (fs.existsSync(kbDir) && fs.existsSync(path.join(kbDir, 'chunks.json'))) {
        fs.mkdirSync(candidate, { recursive: true })
        dataDir = candidate
        break
      }
    } catch { /* try next */ }
  }

  // 回退：创建新目录
  if (!dataDir) {
    for (const base of candidateBaseDirs) {
      const candidate = path.join(base, 'data')
      try {
        fs.mkdirSync(candidate, { recursive: true })
        const testFile = path.join(candidate, '.write_test')
        fs.writeFileSync(testFile, 'ok')
        fs.unlinkSync(testFile)
        dataDir = candidate
        break
      } catch { /* try next */ }
    }
  }

  if (!dataDir) dataDir = path.join(candidateBaseDirs[0] || process.cwd(), 'data')
  }

  const logDir = path.join(dataDir, 'logs')
  const pythonLogFile = path.join(logDir, 'python.log')
  const mainLogFile = path.join(logDir, 'main.log')
  try {
    fs.mkdirSync(logDir, { recursive: true })
  } catch {
    // ignore
  }

  const writeMainLog = (line: string) => {
    try {
      fs.appendFileSync(mainLogFile, line)
    } catch {
      // ignore
    }
  }

  const writePythonLog = (line: string) => {
    try {
      fs.appendFileSync(pythonLogFile, line)
    } catch {
      // ignore
    }
  }

  const startStamp = new Date().toISOString()
  writeMainLog(`\n==== ${startStamp} ====\n`)
  writeMainLog(`PORTABLE_EXECUTABLE_DIR=${portableDir || ''}\n`)
  writeMainLog(`exe=${app.getPath('exe')}\n`)
  writeMainLog(`userData=${app.getPath('userData')}\n`)
  writeMainLog(`dataDir=${dataDir}\n`)
  
  const port = await pickAvailablePort(8000, 8010)
  backendBaseUrl = `http://127.0.0.1:${port}`

  console.log(`Starting Python backend: ${pythonExecutable} ${scriptPath} (port=${port})`)
  writeMainLog(`pythonExecutable=${pythonExecutable}\n`)
  writeMainLog(`scriptPath=${scriptPath}\n`)
  writeMainLog(`port=${port}\n`)
  writePythonLog(`\n==== ${startStamp} ====\n`)
  writePythonLog(`pythonExecutable=${pythonExecutable}\nscriptPath=${scriptPath}\nGB_DATA_DIR=${dataDir}\nGB_PORT=${port}\n`)
  
  pythonProcess = spawn(pythonExecutable, [scriptPath], {
    shell: true,
    // 隐藏终端窗口，但在主进程控制台中输出日志以供排查
    stdio: 'pipe',
    env: {
      ...process.env,
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      GB_DATA_DIR: dataDir,
      GB_PORT: String(port),
    },
  })

  pythonProcess.stdout?.on('data', (data) => {
    console.log(`Python stdout: ${data}`)
    writePythonLog(`[STDOUT] ${data.toString()}`)
  })

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`Python stderr: ${data}`)
    writePythonLog(`[STDERR] ${data.toString()}`)
  })

  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python backend:', err)
    writePythonLog(`[ERROR] Failed to start Python backend: ${String(err)}\n`)
  })

  pythonProcess.on('close', (code) => {
    console.log(`Python backend exited with code ${code}`)
    writePythonLog(`[CLOSE] Python backend exited with code ${code}\n`)
  })
}

function createWindow() {
  let appVersion = ''
  try {
    const pkg = require(path.join(__dirname, '../package.json'))
    appVersion = pkg.version || ''
  } catch { /* ignore */ }
  win = new BrowserWindow({
    width: 1280,
    height: 800,
    icon: path.join(process.env.VITE_PUBLIC, 'favicon.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: true,
      contextIsolation: false,
    },
    title: appVersion ? `游戏策划AI文档助手--${appVersion}` : '游戏策划AI文档助手',
    frame: true,
  })

  // 隐藏顶部默认的英文菜单栏
  win.setMenu(null)

  // Test active push message to Renderer-process.
  win.webContents.on('did-finish-load', () => {
    win?.webContents.send('main-process-message', (new Date()).toLocaleString())
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    win.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    // win.loadFile('dist/index.html')
    win.loadFile(path.join(process.env.DIST, 'index.html'))
  }
}

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
    win = null
  }
})

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

app.whenReady().then(async () => {
  const gotLock = app.requestSingleInstanceLock()
  if (!gotLock) {
    app.quit()
    return
  }

  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  // 设置 IPC 处理程序
  ipcMain.handle('toggle-auto-start', (event, enable) => {
    app.setLoginItemSettings({
      openAtLogin: enable,
      path: app.getPath('exe')
    })
    return app.getLoginItemSettings().openAtLogin
  })

  ipcMain.handle('get-auto-start-status', () => {
    return app.getLoginItemSettings().openAtLogin
  })

  ipcMain.on('show-item-in-folder', (event, filePath) => {
    shell.showItemInFolder(filePath)
  })

  ipcMain.handle('save-file-as', async (event, content, defaultName) => {
    if (!win) return { success: false, error: 'No window' }
    const { canceled, filePath } = await dialog.showSaveDialog(win, {
      defaultPath: defaultName,
    })
    if (canceled || !filePath) {
      return { success: false, error: 'Canceled' }
    }
    try {
      // 如果是 data URI，解码为二进制再写入
      if (typeof content === 'string' && content.startsWith('data:')) {
        const commaIdx = content.indexOf(',')
        if (commaIdx !== -1) {
          const b64 = content.substring(commaIdx + 1)
          const buf = Buffer.from(b64, 'base64')
          fs.writeFileSync(filePath, buf)
          return { success: true, filePath }
        }
      }
      fs.writeFileSync(filePath, content)
      return { success: true, filePath }
    } catch (error: any) {
      return { success: false, error: error.message }
    }
  })

  ipcMain.handle('select-local-image', async () => {
    if (!win) return { success: false, error: 'No window' }
    const { canceled, filePaths } = await dialog.showOpenDialog(win, {
      title: '选择图片',
      filters: [{ name: '图片文件', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'] }],
      properties: ['openFile'],
    })
    if (canceled || filePaths.length === 0) return { success: false, error: 'Canceled' }
    try {
      const buf = fs.readFileSync(filePaths[0])
      const ext = path.extname(filePaths[0]).toLowerCase()
      const mimeMap: Record<string, string> = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.bmp': 'image/bmp' }
      const mime = mimeMap[ext] || 'image/png'
      const base64 = buf.toString('base64')
      return { success: true, dataUri: `data:${mime};base64,${base64}` }
    } catch (error: any) {
      return { success: false, error: error.message }
    }
  })

  ipcMain.handle('test-ai-model', async (_event, modelName: string, apiKey: string, modelId: string) => {
    const https = require('node:https')
    const http = require('node:http')
    const MODEL_ENDPOINTS: Record<string, string> = {
      'DeepSeek': 'https://api.deepseek.com/v1/chat/completions',
      'GPT-4o': 'https://api.openai.com/v1/chat/completions',
      'Kimi': 'https://api.moonshot.cn/v1/chat/completions',
      'GLM': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    }
    const endpoint = MODEL_ENDPOINTS[modelName]
    if (!endpoint) return { success: false, error: `不支持的模型: ${modelName}` }
    if (!apiKey) return { success: false, error: 'API Key 未配置' }
    const body = JSON.stringify({
      model: modelId || modelName.toLowerCase(),
      messages: [{ role: 'user', content: 'Hi' }],
      max_tokens: 5,
    })
    return new Promise((resolve) => {
      const url = new URL(endpoint)
      const mod = url.protocol === 'https:' ? https : http
      const req = mod.request({
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        timeout: 15000,
      }, (res: any) => {
        let data = ''
        res.on('data', (chunk: string) => data += chunk)
        res.on('end', () => {
          if (res.statusCode === 200) resolve({ success: true })
          else resolve({ success: false, error: `HTTP ${res.statusCode}: ${data.substring(0, 200)}` })
        })
      })
      req.on('error', (err: Error) => resolve({ success: false, error: err.message }))
      req.on('timeout', () => { req.destroy(); resolve({ success: false, error: '连接超时' }) })
      req.write(body)
      req.end()
    })
  })

  ipcMain.handle('get-backend-base-url', () => backendBaseUrl)

  // 快捷工具：运行 SVN 更新（支持 TortoiseSVN 和原生 svn）
  ipcMain.handle('run-svn-update', async (_event, folderPath: string, tortoisePath?: string) => {
    try {
      // 优先使用 TortoiseSVN
      if (tortoisePath && tortoisePath.trim()) {
        const tp = tortoisePath.trim().replace(/^"|"$/g, '')
        const tortoiseCmd = `"${tp}" /command:update /path:"${folderPath}" /closeonend:0`
        execSync(tortoiseCmd, { timeout: 120000, shell: 'cmd.exe', stdio: 'ignore' })
        return { success: true, message: '已启动 TortoiseSVN 更新' }
      }
      // 回退：使用原生 svn 命令
      const checkCmd = `chcp 65001 >nul 2>&1 && svn info "${folderPath}" --xml 2>nul`
      try {
        execSync(checkCmd, { encoding: 'utf-8', timeout: 10000, shell: 'cmd.exe', stdio: 'pipe' })
      } catch {
        return { success: false, message: '该路径不是有效的 SVN 工作副本，请确认文件夹已执行过 svn checkout，或在设置中配置 TortoiseSVN 路径' }
      }
      const cmd = `chcp 65001 >nul 2>&1 && svn update "${folderPath}"`
      const result = execSync(cmd, { encoding: 'utf-8', timeout: 120000, shell: 'cmd.exe', maxBuffer: 1024 * 1024 })
      return { success: true, message: (result || '').substring(0, 1000) }
    } catch (err: any) {
      const msg = (err.stderr || err.stdout || err.message || String(err)).substring(0, 1000)
      return { success: false, message: msg }
    }
  })

  // 快捷工具：打开文件夹/程序
  ipcMain.handle('open-path', async (_event, targetPath: string) => {
    try {
      if (targetPath.startsWith('http://') || targetPath.startsWith('https://')) {
        await shell.openExternal(targetPath)
      } else {
        await shell.openPath(targetPath)
      }
      return { success: true }
    } catch (err: any) {
      return { success: false, message: err.message }
    }
  })

  // 快捷工具：选择文件夹
  ipcMain.handle('select-folder', async () => {
    if (!win) return { success: false, error: 'No window' }
    const { canceled, filePaths } = await dialog.showOpenDialog(win, {
      properties: ['openDirectory'],
      title: '选择文件夹'
    })
    if (canceled || filePaths.length === 0) return { success: false, error: 'Canceled' }
    return { success: true, path: filePaths[0] }
  })

  // 重启后端服务
  ipcMain.handle('restart-backend', async () => {
    if (pythonProcess) {
      pythonProcess.kill()
      pythonProcess = null
    }
    // 杀掉占用端口的残留进程
    try {
      execSync('for /f "tokens=5" %a in (\'netstat -ano ^| findstr :8000 ^| findstr LISTENING\') do taskkill /f /pid %a 2>nul', { stdio: 'ignore', shell: 'cmd.exe' })
    } catch { /* ignore */ }
    // 等待 2 秒确保进程完全退出
    await new Promise((r) => setTimeout(r, 2000))
    await startPythonBackend()
    return true
  })

  // 先确保后端启动完成，再创建窗口（防止前端拿到错误的默认端口）
  await startPythonBackend()
  createWindow()
})

// 在应用退出前关闭 Python 进程
app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill()
  }
})
