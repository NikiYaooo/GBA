import { ref } from 'vue'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'
import type { ApiResponse } from '@/types'

export function useAI() {
  const activeModel = ref('DeepSeek')
  const aiResult = ref('')
  const isProcessing = ref(false)
  const iterativePrompt = ref('')

  const models = ref([
    { name: '豆包', type: 'cloud' as const },
    { name: 'DeepSeek', type: 'cloud' as const },
    { name: 'GPT', type: 'cloud' as const },
    { name: 'Gemini', type: 'cloud' as const },
    { name: 'Kimi', type: 'cloud' as const },
    { name: 'GLM', type: 'cloud' as const },
    { name: 'Ollama (本地)', type: 'local' as const },
  ])

  const runQualityCheck = async (content: string, systemPrompt?: string): Promise<string | null> => {
    const r = await axios.post<ApiResponse<string>>(apiUrl('/api/ai/quality-check'), {
      model: activeModel.value, content, system_prompt: systemPrompt || ''
    })
    if (r.data.success) return r.data.data || null
    return null
  }

  const runImitation = async (requirements: string, context = '', useRag = true, format = 'html', templateContent = '', images: string[] = []): Promise<string | null> => {
    const r = await axios.post<ApiResponse<string>>(apiUrl('/api/ai/imitate'), {
      model: activeModel.value, requirements, context, use_rag: useRag, format, template_content: templateContent, images
    })
    if (r.data.success) return r.data.data || null
    return null
  }

  const runLogicCompletion = async (content: string): Promise<string | null> => {
    const r = await axios.post<ApiResponse<string>>(apiUrl('/api/ai/complete-logic'), {
      model: activeModel.value, content
    })
    if (r.data.success) return r.data.data || null
    return null
  }

  const iterate = async (prompt: string): Promise<void> => {
    const res = await runImitation(prompt, aiResult.value, false, 'markdown')
    if (res) aiResult.value = `【迭代修改】\n\n${res}`
  }

  const generateDocTitle = (requirements: string): string => {
    const titleMatch = requirements.match(/(.+?)(系统|活动|玩法|功能|模块)/)
    return titleMatch ? `[${titleMatch[1]}${titleMatch[2]}]策划案` : '[策划案]'
  }

  return {
    activeModel, models, aiResult, isProcessing, iterativePrompt,
    runQualityCheck, runImitation, runLogicCompletion, iterate, generateDocTitle
  }
}
