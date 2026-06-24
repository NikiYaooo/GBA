import { app, BrowserWindow, ipcMain, shell, dialog } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import { spawn, execSync, type ChildProcess } from 'node:child_process'

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
let backendDataDir = ''

// ========== 远程开关 ==========
const SWITCH_URL = 'https://github.com/NikiYaooo/GBA-switch/blob/main/switch.txt'

/**
 * 检查远程开关（从 GitHub blob 页解析 rawLines JSON 字段）。
 * 返回 true 表示允许使用。
 * 网络异常时默认允许（fail open），避免因无法访问 GitHub 导致软件不可用。
 */
async function checkSwitch(): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    const response = await fetch(SWITCH_URL, {
      signal: controller.signal,
      headers: { 'User-Agent': 'Mozilla/5.0' },
    })
    clearTimeout(timeout)
    const html = await response.text()
    // GitHub blob page 将文件内容嵌入 rawLines JSON 字段中
    const match = html.match(/rawLines":\s*\[?\s*"([^"]+)"\s*\]?/)
    if (match) {
      return match[1].trim() === '1'
    }
    return false
  } catch {
    return true // fail open
  }
}

/**
 * 开关前置守卫：在 IPC handler 开头调用，返回 false 时 handler 应拒绝操作。
 */
async function guardSwitch(): Promise<boolean> {
  const ok = await checkSwitch()
  if (!ok) {
    // 通知渲染进程显示权限不足
    win?.webContents.send('switch-denied', '软件权限不足')
  }
  return ok
}

/**
 * 确保端口 8000 可用：杀掉占用进程后等待，然后绑定确认。
 */
async function ensurePort8000(): Promise<number> {
  // 杀掉占用 8000 端口的进程
  try {
    execSync(
      'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :8000 ^| findstr LISTENING\') do taskkill /f /pid %a 2>nul',
      { stdio: 'ignore', shell: 'cmd.exe', timeout: 3000 }
    )
  } catch { /* ignore */ }
  // 等待 TIME_WAIT 释放
  await new Promise(r => setTimeout(r, 1500))
  // 最终确认 8000 可用
  return 8000
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
async function startPythonBackend(): Promise<boolean> {
  // 杀掉占用 8000 端口的旧 Python 进程（防止旧版本后端干扰）
  try {
    execSync(
      'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :8000 ^| findstr LISTENING\') do taskkill /f /pid %a 2>nul',
      { stdio: 'ignore', shell: 'cmd.exe', timeout: 3000 }
    )
  } catch { /* ignore */ }

  // ========== 1. 查找 Python 可执行文件 ==========
  let pythonExecutable: string | null = null
  let isVenv = false

  // 优先查找 .venv 环境（便携版同目录 / 开发目录）
  const portableDir = process.env.PORTABLE_EXECUTABLE_DIR
  const venvBaseDirs = [
    ...(portableDir ? [portableDir] : []),
    process.cwd(),
    path.join(process.cwd(), '..'),
    path.join(app.getAppPath(), '..', '..'),
    'E:\\game_builder',
  ]

  for (const base of venvBaseDirs) {
    const candidate = path.join(base, '.venv', 'Scripts', 'python.exe')
    if (fs.existsSync(candidate)) {
      pythonExecutable = candidate
      isVenv = true
      break
    }
  }

  // 回退到系统 Python
  if (!pythonExecutable) {
    for (const name of ['python', 'python3']) {
      try {
        execSync(`${name} --version`, { stdio: 'ignore', timeout: 3000 })
        pythonExecutable = name
        break
      } catch { /* try next */ }
    }
  }

  // ========== 2. Python 未安装 ==========
  if (!pythonExecutable) {
    await dialog.showMessageBox({
      type: 'error',
      title: 'Python 环境缺失',
      message: '未检测到 Python 环境',
      detail: 'Game builder aide 需要 Python 3.10+ 才能运行后端服务。\n\n请先安装 Python，然后运行程序所在目录下的 setup_env.bat 安装依赖。\n\n下载地址：https://www.python.org/downloads/',
    })
    return false
  }

  // ========== 3. 检查依赖是否完整 ==========
  try {
    execSync(`"${pythonExecutable}" -c "import fastapi, uvicorn, openai, docx, PIL, requests, pydantic, dotenv, markdown, httpx, openpyxl"`, {
      stdio: 'ignore', timeout: 10000,
    })
  } catch {
    const btn = await dialog.showMessageBox({
      type: 'warning',
      title: 'Python 依赖缺失',
      message: '检测到 Python 但缺少必要依赖包',
      detail: '缺少 fastapi、uvicorn、openai 等关键库。\n\n首次安装需要下载约 2GB 数据（含 PyTorch 等），请确保网络畅通。\n安装时间取决于网速，通常约 10-30 分钟。\n\n是否一键安装所有依赖？',
      buttons: ['一键安装依赖', '退出'],
      defaultId: 0,
      cancelId: 1,
    })
    if (btn.response === 1) return false

    // 执行安装
    const pipCmd = isVenv
      ? `"${path.join(path.dirname(pythonExecutable), 'pip.exe')}"`
      : `"${pythonExecutable}" -m pip`

    const reqPaths = [
      ...(portableDir ? [path.join(portableDir, 'requirements.txt')] : []),
      path.join(process.cwd(), 'requirements.txt'),
    ]
    let reqPath = ''
    for (const rp of reqPaths) {
      if (fs.existsSync(rp)) { reqPath = rp; break }
    }

    try {
      const installCmd = reqPath
        ? `${pipCmd} install -r "${reqPath}"`
        : `${pipCmd} install fastapi uvicorn python-multipart python-docx markdown openai pydantic python-dotenv requests sentence-transformers rank_bm25 jieba dashscope Pillow`
      execSync(installCmd, { timeout: 600000, stdio: 'pipe', maxBuffer: 10 * 1024 * 1024 })
    } catch (e: any) {
      await dialog.showMessageBox({
        type: 'error',
        title: '安装失败',
        message: '依赖安装失败',
        detail: `请手动运行 setup_env.bat 安装依赖。\n错误：${(e.message || String(e)).substring(0, 300)}`,
      })
      return false
    }
  }

  // 在开发环境中，api 目录在项目根目录
  // 在打包后，api 目录在 resources 目录下
  const scriptPath = app.isPackaged 
    ? path.join(process.resourcesPath, 'api/main.py')
    : path.join(process.cwd(), 'api/main.py')

  const exeDir = process.env.PORTABLE_EXECUTABLE_DIR
  const candidateBaseDirs = app.isPackaged
    ? [exeDir, path.dirname(app.getPath('exe')), app.getPath('userData')].filter(Boolean) as string[]
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
  // 也检查 exeDir 的父目录下其他 release 文件夹
  if (exeDir) {
    const parentDir = path.dirname(exeDir)
    try {
      const entries = fs.readdirSync(parentDir, { withFileTypes: true })
      for (const entry of entries.reverse()) {
        if (entry.isDirectory() && entry.name !== path.basename(exeDir)) {
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
  backendDataDir = dataDir
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
  writeMainLog(`PORTABLE_EXECUTABLE_DIR=${exeDir || ''}\n`)
  writeMainLog(`exe=${app.getPath('exe')}\n`)
  writeMainLog(`userData=${app.getPath('userData')}\n`)
  writeMainLog(`dataDir=${dataDir}\n`)
  
  const port = await ensurePort8000()
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

  let processExited = false
  let exitCode: number | null = null
  pythonProcess.on('close', (code) => {
    processExited = true
    exitCode = code
    console.log(`Python backend exited with code ${code}`)
    writePythonLog(`[CLOSE] Python backend exited with code ${code}\n`)
  })

  // 等待 3 秒，检查 Python 进程是否立即崩溃
  await new Promise(r => setTimeout(r, 3000))

  if (processExited) {
    // 读取日志中的 stderr 输出
    let stderrLog = ''
    try {
      if (fs.existsSync(pythonLogFile)) {
        const raw = fs.readFileSync(pythonLogFile, 'utf-8')
        const lines = raw.split('\n').filter(l => l.startsWith('[STDERR]'))
        stderrLog = lines.join('\n').substring(0, 2000)
      }
    } catch { /* ignore */ }

    const detail = [
      `Python 路径: ${pythonExecutable}`,
      `脚本路径: ${scriptPath}`,
      `数据目录: ${dataDir}`,
      `.venv: ${isVenv ? '是' : '否'}`,
      `退出码: ${exitCode}`,
      stderrLog ? `\n错误日志:\n${stderrLog}` : '\n（无 stderr 输出，可能是 Python 未安装或路径错误）',
    ].join('\n')

    await dialog.showMessageBox({
      type: 'error',
      title: 'Python 后端启动失败',
      message: 'Python 进程在启动后 3 秒内退出了',
      detail,
    })
    return false
  }

  return true
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
    title: appVersion ? `Game builder aide--${appVersion}` : 'Game builder aide',
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
    if (!await guardSwitch()) return { success: false, error: '软件权限不足' }
    const https = require('node:https')
    const http = require('node:http')

    // 豆包：使用 Responses API
    if (modelName === '豆包') {
      if (!apiKey) return { success: false, error: 'API Key 未配置' }
      const endpoint = 'https://ark.cn-beijing.volces.com/api/v3/responses'
      const body = JSON.stringify({
        model: modelId || 'doubao',
        input: [{ role: 'user', content: [{ type: 'input_text', text: 'Hi' }] }],
        max_output_tokens: 5,
      })
      return new Promise((resolve) => {
        const url = new URL(endpoint)
        const req = https.request({
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
    }

    // Ollama：本地调用检查
    if (modelName === 'Ollama (本地)') {
      const baseUrl = (modelId || 'http://localhost:11434').replace(/\/+$/, '')
      try {
        const r = await fetch(`${baseUrl}/api/tags`)
        if (r.ok) return { success: true }
        return { success: false, error: `HTTP ${r.status}` }
      } catch (e: any) {
        return { success: false, error: e.message }
      }
    }

    const MODEL_ENDPOINTS: Record<string, string> = {
      'DeepSeek': 'https://api.deepseek.com/v1/chat/completions',
      'GPT': 'https://api.openai.com/v1/chat/completions',
      'Kimi': 'https://api.moonshot.cn/v1/chat/completions',
      'GLM': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
      'Gemini': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
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

  // 读取后端诊断日志
  ipcMain.handle('get-backend-diagnostics', () => {
    if (!backendDataDir) return { logs: '数据目录未初始化', error: '' }
    const logDir = path.join(backendDataDir, 'logs')
    let mainLog = '', pythonLog = '', pythonRunning = false, pythonPath = ''
    try {
      const ml = path.join(logDir, 'main.log')
      if (fs.existsSync(ml)) mainLog = fs.readFileSync(ml, 'utf-8').split('\n').slice(-30).join('\n')
    } catch { /* ignore */ }
    try {
      const pl = path.join(logDir, 'python.log')
      if (fs.existsSync(pl)) pythonLog = fs.readFileSync(pl, 'utf-8').split('\n').slice(-30).join('\n')
    } catch { /* ignore */ }
    try {
      if (pythonProcess && !pythonProcess.killed && pythonProcess.exitCode === null) {
        pythonRunning = true
        pythonPath = pythonProcess.spawnfile
      }
    } catch { /* ignore */ }
    return { mainLog, pythonLog, pythonRunning, pythonPath, dataDir: backendDataDir }
  })

  // 远程开关：退出应用
  ipcMain.handle('quit-app', () => { app.quit() })

  // 快捷工具：运行 SVN 更新（支持 TortoiseSVN 和原生 svn）
  ipcMain.handle('run-svn-update', async (_event, folderPath: string, tortoisePath?: string) => {
    if (!await guardSwitch()) return { success: false, message: '软件权限不足' }
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
  const backendReady = await startPythonBackend()
  if (!backendReady) {
    app.quit()
    return
  }

  createWindow()

  // 异步检测远程开关，不阻塞窗口启动（用户可先看到界面）
  checkSwitch().then((ok) => {
    if (!ok) {
      dialog.showMessageBox({
        type: 'error',
        title: '权限不足',
        message: '软件权限已被远程关闭',
      }).then(() => app.quit())
    }
  })
})

// 在应用退出前关闭 Python 进程
app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill()
  }
})
