/** 文本模型定义（AI 仿写/质检/逻辑补完等） */
export const TEXT_MODELS = [
  { name: 'DeepSeek', type: 'cloud' as const },
  { name: '豆包', type: 'cloud' as const },
  { name: 'GPT', type: 'cloud' as const },
  { name: 'Gemini', type: 'cloud' as const },
  { name: 'Kimi', type: 'cloud' as const },
  { name: 'GLM', type: 'cloud' as const },
  { name: 'Ollama (本地)', type: 'local' as const },
]

/** 图片模型定义（文生图/图生图/修改） */
export const IMAGE_MODELS = [
  { name: 'GPT-Image 2', type: 'cloud' as const },
  { name: 'Qwen-Image 2', type: 'cloud' as const },
  { name: '豆包Seedream', type: 'cloud' as const },
  { name: 'Stable Diffusion（本地）', type: 'local' as const },
]

/** 默认选中的模型 */
export const DEFAULT_TEXT_MODEL = 'DeepSeek'
export const DEFAULT_IMAGE_MODEL = 'GPT-Image 2'
