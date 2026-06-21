"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { createPortal } from "react-dom"
import {
  ArrowRight, ArrowLeft, X, MousePointer2, PanelLeft,
  Workflow, Keyboard, Sparkles, ChevronRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"

const STORAGE_KEY = "wf-onboarding-done"

interface GuideStep {
  title: string
  description: string
  icon: typeof Sparkles
  target?: string // data-onboarding attribute selector
  highlight?: "center" | "left" | "right"
}

const STEPS: GuideStep[] = [
  {
    title: "欢迎使用工作流编辑器",
    description: "通过可视化拖拽组合 AI 处理模块，轻松构建自动化文档处理流程。接下来花 30 秒了解核心功能。",
    icon: Sparkles,
    highlight: "center",
  },
  {
    title: "模块面板",
    description: "左侧列出了所有可用的 AI 处理模块，分为「输入」「处理」「输出」三类。将模块拖拽到画布即可添加节点，也可以直接点击快速添加。",
    icon: PanelLeft,
    target: "[data-onboarding='module-panel']",
    highlight: "left",
  },
  {
    title: "画布区域",
    description: "在画布上自由排列和连接节点。拖拽节点可移动位置，从底部连接点拖拽到另一节点顶部可创建连线。滚轮缩放，拖拽平移。",
    icon: Workflow,
    target: "[data-onboarding='canvas']",
    highlight: "center",
  },
  {
    title: "右键菜单",
    description: "在节点、连线或画布空白处右键点击，可打开上下文菜单。支持配置节点、复制、删除、自动排列等操作。",
    icon: MousePointer2,
    highlight: "center",
  },
  {
    title: "工具栏",
    description: "顶部工具栏提供「自动排列」（智能拓扑排序布局）和「删除选中」按钮。编辑完成后点击「保存」持久化工作流。",
    icon: ChevronRight,
    target: "[data-onboarding='toolbar']",
    highlight: "right",
  },
  {
    title: "快捷键",
    description: "Delete/Backspace 删除选中节点 · Shift+点击多选 · 右键打开菜单 · Ctrl+A 全选 · 空格+拖拽平移画布",
    icon: Keyboard,
    highlight: "center",
  },
]

interface OnboardingGuideProps {
  onComplete: () => void
}

export function OnboardingGuide({ onComplete }: OnboardingGuideProps) {
  const [step, setStep] = useState(0)
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)
  const [show, setShow] = useState(false)
  const animFrameRef = useRef<number>(0)

  const currentStep = STEPS[step]

  // Update target rect on step change and window resize
  const updateTargetRect = useCallback(() => {
    if (!currentStep.target) {
      setTargetRect(null)
      return
    }
    const el = document.querySelector(currentStep.target)
    if (el) {
      setTargetRect(el.getBoundingClientRect())
    } else {
      setTargetRect(null)
    }
  }, [currentStep.target])

  useEffect(() => {
    updateTargetRect()
    const onResize = () => updateTargetRect()
    window.addEventListener("resize", onResize)

    // Poll for target element appearance (it may render after mount)
    const interval = setInterval(updateTargetRect, 200)

    return () => {
      window.removeEventListener("resize", onResize)
      clearInterval(interval)
    }
  }, [updateTargetRect])

  // Entrance animation
  useEffect(() => {
    const t = setTimeout(() => setShow(true), 100)
    return () => clearTimeout(t)
  }, [])

  function handleNext() {
    if (step < STEPS.length - 1) {
      setStep(s => s + 1)
    } else {
      handleFinish()
    }
  }

  function handlePrev() {
    if (step > 0) setStep(s => s - 1)
  }

  function handleFinish() {
    try { localStorage.setItem(STORAGE_KEY, "1") } catch {}
    onComplete()
  }

  // Spotlight padding
  const PAD = 8

  function renderSpotlight() {
    if (!targetRect) return null

    const x = targetRect.left - PAD
    const y = targetRect.top - PAD
    const w = targetRect.width + PAD * 2
    const h = targetRect.height + PAD * 2

    return (
      <div
        className="absolute rounded-xl pointer-events-none transition-all duration-500 ease-out"
        style={{
          left: x,
          top: y,
          width: w,
          height: h,
          boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.55)",
          border: "2px solid rgba(59, 130, 246, 0.6)",
          zIndex: 10001,
        }}
      />
    )
  }

  function renderCard() {
    const Icon = currentStep.icon
    const isCenter = currentStep.highlight === "center" || !targetRect
    const isLeft = currentStep.highlight === "left"
    const isRight = currentStep.highlight === "right"

    let cardStyle: React.CSSProperties = {}
    if (isCenter || !targetRect) {
      cardStyle = {
        position: "fixed",
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
      }
    } else if (isLeft && targetRect) {
      cardStyle = {
        position: "fixed",
        left: targetRect.right + 24,
        top: Math.max(80, targetRect.top + targetRect.height / 2 - 120),
        transform: "none",
      }
    } else if (isRight && targetRect) {
      cardStyle = {
        position: "fixed",
        right: window.innerWidth - targetRect.left + 24,
        top: Math.max(80, targetRect.top + targetRect.height / 2 - 120),
        transform: "none",
      }
    }

    return (
      <div
        style={{ ...cardStyle, zIndex: 10002, maxWidth: 380 }}
        className={`bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden transition-all duration-300 ${show ? "opacity-100 scale-100" : "opacity-0 scale-95"}`}
      >
        {/* Header with gradient */}
        <div className="bg-gradient-to-r from-blue-500 to-indigo-600 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/20 rounded-lg">
              <Icon className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="text-white font-semibold text-sm">{currentStep.title}</h3>
              <p className="text-white/70 text-xs">{step + 1} / {STEPS.length}</p>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            {currentStep.description}
          </p>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <Button variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={handleFinish}>
            跳过
          </Button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <Button variant="outline" size="sm" className="text-xs" onClick={handlePrev}>
                <ArrowLeft className="h-3 w-3 mr-1" /> 上一步
              </Button>
            )}
            <Button size="sm" className="text-xs" onClick={handleNext}>
              {step < STEPS.length - 1 ? (
                <>下一步 <ArrowRight className="h-3 w-3 ml-1" /></>
              ) : (
                <>开始使用 <Sparkles className="h-3 w-3 ml-1" /></>
              )}
            </Button>
          </div>
        </div>

        {/* Step dots */}
        <div className="flex justify-center gap-1.5 pb-3">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === step ? "w-6 bg-blue-500" : i < step ? "w-1.5 bg-blue-300" : "w-1.5 bg-slate-200 dark:bg-slate-700"
              }`}
            />
          ))}
        </div>
      </div>
    )
  }

  return createPortal(
    <div className="fixed inset-0 z-[10000]" style={{ pointerEvents: "auto" }}>
      {/* Dark overlay with cutout */}
      <div className="absolute inset-0 bg-black/50 transition-opacity duration-300" onClick={handleFinish} />
      {/* Spotlight */}
      {renderSpotlight()}
      {/* Card */}
      {renderCard()}
    </div>,
    document.body,
  )
}

/**
 * Check if onboarding should be shown.
 * Returns true if user hasn't completed it before.
 */
export function shouldShowOnboarding(): boolean {
  if (typeof window === "undefined") return false
  try {
    return !localStorage.getItem(STORAGE_KEY)
  } catch {
    return false
  }
}

/**
 * Reset onboarding so it shows again next time.
 */
export function resetOnboarding() {
  try { localStorage.removeItem(STORAGE_KEY) } catch {}
}
