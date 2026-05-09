/// <reference types="vite/client" />

interface Window {
  electronAPI?: {
    toggleAutoStart: (enable: boolean) => Promise<boolean>;
    getAutoStartStatus: () => Promise<boolean>;
    showItemInFolder: (filePath: string) => void;
    saveFileAs: (content: string, defaultName: string) => Promise<{ success: boolean; filePath?: string; error?: string }>;
    getBackendBaseUrl: () => Promise<string>;
    restartBackend: () => Promise<boolean>;
    selectLocalImage: () => Promise<{ success: boolean; dataUri?: string; error?: string }>;
    testAIModel: (modelName: string, apiKey: string, modelId: string) => Promise<{ success: boolean; error?: string }>;
    runSvnUpdate: (folderPath: string, tortoisePath?: string) => Promise<{ success: boolean; message?: string }>;
    openPath: (targetPath: string) => Promise<{ success: boolean; message?: string }>;
    selectFolder: () => Promise<{ success: boolean; path?: string; error?: string }>;
  }
}
