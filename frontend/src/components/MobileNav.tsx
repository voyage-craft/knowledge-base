"use client"

import { useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import {
  Sheet, SheetTrigger, SheetContent, SheetTitle,
} from "@/components/ui/sheet"
import { useUser } from "@/lib/user-context"
import {
  FileText, MessageSquare, BookOpen, Settings,
  Moon, Sun, LogOut, Menu, Network, Upload, Workflow,
} from "lucide-react"
import { apiFetch } from "@/lib/api-client"
import { useDarkMode } from "@/lib/use-dark-mode"

const NAV_ITEMS = [
  { href: "/documents", label: "文档管理", icon: FileText },
  { href: "/graph", label: "知识图谱", icon: Network },
  { href: "/import", label: "批量导入", icon: Upload },
  { href: "/workflows", label: "AI 工作流", icon: Workflow },
  { href: "/chat", label: "AI 对话", icon: MessageSquare },
  { href: "/settings", label: "设置", icon: Settings },
]

export function MobileNav() {
  const router = useRouter()
  const pathname = usePathname()
  const user = useUser()
  const [open, setOpen] = useState(false)
  const { dark, toggleDark } = useDarkMode()

  function navigate(href: string) {
    setOpen(false)
    router.push(href)
  }

  async function handleLogout() {
    setOpen(false)
    await apiFetch("/api/auth/logout", { method: "POST" }).catch(() => {})
    router.push("/login")
  }

  return (
    <div className="md:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          render={
            <Button variant="ghost" size="icon" className="h-9 w-9" />
          }
        >
          <Menu className="h-5 w-5" />
        </SheetTrigger>
        <SheetContent side="left" className="w-60 p-0">
          <SheetTitle className="sr-only">导航菜单</SheetTitle>

          {/* Logo */}
          <div className="flex items-center gap-2.5 px-5 py-4 border-b">
            <div className="p-1.5 rounded-lg bg-blue-600">
              <BookOpen className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-sm tracking-tight">知识库</span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-3 space-y-0.5">
            {NAV_ITEMS.map(item => {
              const active = pathname === item.href || pathname.startsWith(item.href + "/")
              return (
                <button
                  key={item.href}
                  onClick={() => navigate(item.href)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                    active
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-foreground/70 hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </button>
              )
            })}
          </nav>

          {/* Footer */}
          <div className="px-3 py-3 border-t space-y-1">
            <button
              onClick={toggleDark}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-foreground/70 hover:bg-muted transition-colors"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              {dark ? "浅色模式" : "深色模式"}
            </button>

            <div className="flex items-center gap-2.5 px-3 py-2">
              <div className="h-6 w-6 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-medium shrink-0">
                {user.username.charAt(0).toUpperCase()}
              </div>
              <span className="flex-1 text-sm truncate">{user.username}</span>
            </div>

            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              退出登录
            </button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
