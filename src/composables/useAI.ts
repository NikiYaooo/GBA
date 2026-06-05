import { ref } from 'vue'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'
import type { ApiResponse } from '@/types'
import { TEXT_MODELS, DEFAULT_TEXT_MODEL } from '@/model-defs'

export interface ImitationConflict {
  level: string
  paragraph: string
  suggestion: string
  source_file: string
}

export interface ImitationMeta {
  knowledge_coverage: number | null
  consistency_score: number | null
  conflicts: ImitationConflict[]
}

export function useAI() {
  const activeModel = ref(DEFAULT_TEXT_MODEL)
  const aiResult = ref('')
  const isProcessing = ref(false)
  const iterativePrompt = ref('')

  const models = ref([...TEXT_MODELS])
  const imitationMeta = ref<ImitationMeta | null>(null)

  // 迭代修改相关
  const iterationHistory = ref<{
    instruction: string
    targetSection: string
    replacement: string
    timestamp: number
  }[]>([])
  const showIterationPanel = ref(false)
  const iterationInput = ref('')
  const isIterating = ref(false)

  const runQualityCheck = async (content: string, systemPrompt?: string): Promise<string | null> => {
    const r = await axios.post<ApiResponse<string>>(apiUrl('/api/ai/quality-check'), {
      model: activeModel.value, content, system_prompt: systemPrompt || ''
    })
    if (r.data.success) return r.data.data || null
    return null
  }

  const runImitation = async (requirements: string, context = '', useRag = true, format = 'html', templateContent = '', images: string[] = [], projectId = '', kbOnly = false, citeSources = false): Promise<string | null> => {
    const r = await axios.post<any>(apiUrl('/api/ai/imitate'), {
      model: activeModel.value, requirements, context, use_rag: useRag, format, template_content: templateContent, images,
      project_id: projectId || undefined, kb_only: kbOnly, cite_sources: citeSources
    })
    if (r.data.success) {
      if (r.data.metadata) {
        imitationMeta.value = r.data.metadata as ImitationMeta
      }
      return r.data.data || null
    }
    imitationMeta.value = null
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

  const confirmGeneration = async (content: string, projectId: string) => {
    if (!content || !projectId) return null
    try {
      const r = await axios.post(apiUrl('/api/ai/confirm-generation'), {
        content, project_id: projectId
      })
      if (r.data.success) {
        return r.data.data
      }
      return null
    } catch (e) {
      console.error('确认生成失败:', e)
      return null
    }
  }

  const clearImitationMeta = () => {
    imitationMeta.value = null
  }

  const runIteration = async (
    fullDoc: string,
    instruction: string,
    mode: 'section' | 'selection' | 'full' = 'section',
    targetSection?: string,
    selectionContext?: { selected: string; before: string; after: string },
    projectId?: string,
  ): Promise<string | null> => {
    isIterating.value = true
    try {
      const r = await axios.post(apiUrl('/api/ai/imitate-iterate'), {
        model: activeModel.value,
        full_doc: fullDoc,
        instruction,
        mode,
        target_section: targetSection || '',
        selection_context: selectionContext || null,
        project_id: projectId || undefined,
      })
      if (r.data.success && r.data.data?.replacement) {
        iterationHistory.value.push({
          instruction,
          targetSection: targetSection || '',
          replacement: r.data.data.replacement,
          timestamp: Date.now(),
        })
        return r.data.data.replacement
      }
      return null
    } catch (e: any) {
      console.error('迭代修改失败:', e)
      return null
    } finally {
      isIterating.value = false
    }
  }

  return {
    activeModel, models, aiResult, isProcessing, iterativePrompt,
    runQualityCheck, runImitation, runLogicCompletion, iterate, generateDocTitle,
    runIteration, iterationHistory, imitationMeta, confirmGeneration, clearImitationMeta,
    showIterationPanel, iterationInput, isIterating,
  }
}
