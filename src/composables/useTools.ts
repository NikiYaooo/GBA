import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl } from '@/utils/api'
import type { SVNConfig, NavConfig, Reminder } from '@/types'

export function useTools() {
  const showToolsDialog = ref(false)
  const showSvnDialog = ref(false)
  const showNavDialog = ref(false)
  const showAddSvnDialog = ref(false)
  const showAddNavDialog = ref(false)
  const svnConfigs = ref<SVNConfig[]>([])
  const navConfigs = ref<NavConfig[]>([])
  const svnUpdating = ref('')
  const newSvnName = ref('')
  const newSvnPath = ref('')
  const newNavName = ref('')
  const newNavPath = ref('')
  const svnOpenAfterUpdate = ref(true)
  const reminders = ref<Reminder[]>([])
  const showReminderDialog = ref(false)
  const editingReminder = ref<any>(null)

  const loadConfig = async () => {
    try {
      const r = await axios.get(apiUrl('/api/tools/config'))
      if (r.data.success) {
        svnConfigs.value = r.data.data.svn || []
        navConfigs.value = r.data.data.nav || []
      }
    } catch { /* */ }
  }

  const saveConfig = async () => {
    try {
      await axios.put(apiUrl('/api/tools/config'), {
        svn: svnConfigs.value,
        nav: navConfigs.value
      })
    } catch { /* */ }
  }

  const addSvn = async (path: string) => {
    if (!newSvnName.value.trim()) { ElMessage.warning('请输入名称'); return }
    svnConfigs.value.push({
      id: Date.now().toString(36),
      name: newSvnName.value.trim(),
      path
    })
    newSvnName.value = ''
    showAddSvnDialog.value = false
    await saveConfig()
    ElMessage.success('已添加')
  }

  const removeSvn = async (id: string) => {
    svnConfigs.value = svnConfigs.value.filter(s => s.id !== id)
    await saveConfig()
  }

  const runSvnUpdate = async (item: SVNConfig, tortoisePath: string) => {
    const api = (window as any).electronAPI
    if (!api?.runSvnUpdate) { ElMessage.warning('仅桌面应用可用'); return }
    svnUpdating.value = item.id
    try {
      const r = await api.runSvnUpdate(item.path, tortoisePath)
      if (r.success) {
        ElMessage.success(tortoisePath ? `已启动 TortoiseSVN 更新 ${item.name}` : `${item.name} SVN更新成功`)
        if (svnOpenAfterUpdate.value && api.openPath) api.openPath(item.path)
      } else {
        ElMessage.warning(`${item.name} SVN更新失败: ${r.message || ''}`)
      }
    } catch (e: any) {
      ElMessage.error('SVN更新出错: ' + (e.message || ''))
    } finally { svnUpdating.value = '' }
  }

  const selectFolder = async (): Promise<string | null> => {
    const api = (window as any).electronAPI
    if (!api?.selectFolder) { ElMessage.warning('仅桌面应用可用'); return null }
    const result = await api.selectFolder()
    return result?.success ? result.path : null
  }

  const addNav = async () => {
    if (!newNavName.value.trim() || !newNavPath.value.trim()) {
      ElMessage.warning('请填写名称和路径'); return
    }
    navConfigs.value.push({
      id: Date.now().toString(36),
      name: newNavName.value.trim(),
      path: newNavPath.value.trim()
    })
    newNavName.value = ''
    newNavPath.value = ''
    showAddNavDialog.value = false
    await saveConfig()
    ElMessage.success('已添加')
  }

  const removeNav = async (id: string) => {
    navConfigs.value = navConfigs.value.filter(n => n.id !== id)
    await saveConfig()
  }

  const openNavItem = async (item: NavConfig) => {
    const api = (window as any).electronAPI
    if (!api?.openPath) { ElMessage.warning('仅桌面应用可用'); return }
    const r = await api.openPath(item.path)
    if (!r.success) ElMessage.warning('打开失败: ' + (r.message || ''))
  }

  // 提醒
  const loadReminders = async () => {
    try {
      const r = await axios.get(apiUrl('/api/reminders'))
      if (r.data.success) reminders.value = r.data.data || []
    } catch { /* */ }
  }

  const saveReminder = async (data: { content: string; month: number | null; day: number | null; hour: number; minute: number }) => {
    try {
      if (editingReminder.value) {
        await axios.put(apiUrl(`/api/reminders/${editingReminder.value.id}`), data)
        ElMessage.success('提醒已更新')
      } else {
        await axios.post(apiUrl('/api/reminders'), data)
        ElMessage.success('提醒已添加')
      }
      editingReminder.value = null
      await loadReminders()
    } catch { ElMessage.error('操作失败') }
  }

  const deleteReminder = async (id: string) => {
    try {
      await axios.delete(apiUrl(`/api/reminders/${id}`))
      await loadReminders()
      ElMessage.success('已删除')
    } catch { ElMessage.error('删除失败') }
  }

  const openReminderDialog = (reminder: any = null) => {
    editingReminder.value = reminder
    showReminderDialog.value = true
  }

  const openTools = () => { showToolsDialog.value = true; loadConfig(); loadReminders() }

  return {
    showToolsDialog, showSvnDialog, showNavDialog, showAddSvnDialog, showAddNavDialog,
    svnConfigs, navConfigs, svnUpdating, newSvnName, newSvnPath, newNavName, newNavPath,
    svnOpenAfterUpdate,
    reminders, showReminderDialog, editingReminder,
    loadConfig, saveConfig, addSvn, removeSvn, runSvnUpdate, selectFolder, addNav, removeNav, openNavItem, openTools,
    loadReminders, saveReminder, deleteReminder, openReminderDialog,
  }
}
