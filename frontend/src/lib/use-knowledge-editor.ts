"use client"

import { useEditor, type Editor, type Content } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Placeholder from "@tiptap/extension-placeholder"
import Underline from "@tiptap/extension-underline"
import Highlight from "@tiptap/extension-highlight"
import TaskList from "@tiptap/extension-task-list"
import TaskItem from "@tiptap/extension-task-item"
import TextAlign from "@tiptap/extension-text-align"
import Mathematics from "@tiptap/extension-mathematics"
import CharacterCount from "@tiptap/extension-character-count"
import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight"
import { common, createLowlight } from "lowlight"

// Shared lowlight instance — created once at module scope
const lowlight = createLowlight(common)

interface UseKnowledgeEditorOptions {
  /** Initial editor content (JSON object or HTML string) */
  content?: Content
  /** Whether the editor is editable (default: true) */
  editable?: boolean
  /** Called on every content update with the editor instance */
  onUpdate?: (editor: Editor) => void
  /** Placeholder text shown when editor is empty (omit to disable Placeholder extension) */
  placeholder?: string
  /** Enable CharacterCount extension (default: true) */
  enableCharacterCount?: boolean
  /** CSS class applied to the editor's ProseMirror element */
  className?: string
}

/**
 * Custom hook encapsulating the shared TipTap editor configuration used by
 * both the editor page and the document preview page.
 *
 * This avoids duplicating the extension list, lowlight instance, and
 * editorProps boilerplate across multiple pages.
 */
export function useKnowledgeEditor(options: UseKnowledgeEditorOptions = {}) {
  const {
    content,
    editable = true,
    onUpdate,
    placeholder,
    enableCharacterCount = true,
    className = "prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none focus:outline-none min-h-[600px] px-8 py-6",
  } = options

  return useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({ codeBlock: false }),
      ...(placeholder ? [Placeholder.configure({ placeholder })] : []),
      Underline,
      Highlight.configure({ multicolor: true }),
      TaskList,
      TaskItem.configure({ nested: true }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Mathematics,
      ...(enableCharacterCount ? [CharacterCount] : []),
      CodeBlockLowlight.configure({ lowlight }),
    ],
    content,
    editable,
    editorProps: {
      attributes: {
        class: className,
      },
    },
    onUpdate: onUpdate ? ({ editor }) => onUpdate(editor) : undefined,
  })
}
