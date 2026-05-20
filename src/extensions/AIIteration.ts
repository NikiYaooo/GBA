import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

export interface AIExtensionOptions {
  onModifySection: (title: string) => void
}

/**
 * AI 迭代修改的 TipTap 扩展。
 * 提供 commands: aiModifySection, aiModifySelection
 * 并在每个 h2/h3 标题旁注入修改按钮。
 */
export const AIExtension = Extension.create<AIExtensionOptions>({
  name: 'aiIteration',

  addOptions() {
    return {
      onModifySection: () => {},
    }
  },

  addCommands() {
    return {
      aiModifySection:
        (title: string) =>
        ({ editor }: any) => {
          this.options.onModifySection(title)
          return true
        },
      aiModifySelection:
        () =>
        ({ editor }: any) => {
          const { from, to } = editor.state.selection
          if (from === to) return false
          const selected = editor.state.doc.textBetween(from, to)
          const before = editor.state.doc.textBetween(Math.max(0, from - 200), from)
          const after = editor.state.doc.textBetween(to, Math.min(editor.state.doc.content.size, to + 200))
          window.dispatchEvent(new CustomEvent('ai-modify-selection', {
            detail: { selected, before, after },
          }))
          return true
        },
    } as any
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('aiIteration'),
        props: {
          handleClickOn: (view: any, pos: number, node: any) => {
            return false
          },
        },
      }),
    ]
  },
})
