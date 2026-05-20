import { ipcRenderer } from 'electron'

;(window as any).electronAPI = {
  toggleAutoStart: (enable: boolean) => ipcRenderer.invoke('toggle-auto-start', enable),
  getAutoStartStatus: () => ipcRenderer.invoke('get-auto-start-status'),
  showItemInFolder: (filePath: string) => ipcRenderer.send('show-item-in-folder', filePath),
  saveFileAs: (content: string, defaultName: string) => ipcRenderer.invoke('save-file-as', content, defaultName),
  getBackendBaseUrl: () => ipcRenderer.invoke('get-backend-base-url'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  selectLocalImage: () => ipcRenderer.invoke('select-local-image'),
  testAIModel: (modelName: string, apiKey: string, modelId: string) => ipcRenderer.invoke('test-ai-model', modelName, apiKey, modelId),
  runSvnUpdate: (folderPath: string, tortoisePath?: string) => ipcRenderer.invoke('run-svn-update', folderPath, tortoisePath),
  openPath: (targetPath: string) => ipcRenderer.invoke('open-path', targetPath),
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  quitApp: () => ipcRenderer.invoke('quit-app'),
  onSwitchDenied: (callback: (msg: string) => void) => {
    ipcRenderer.on('switch-denied', (_event, msg) => callback(msg))
  },
}
