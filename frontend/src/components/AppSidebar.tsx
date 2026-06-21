"use client"

import { useRouter, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useUser } from "@/lib/user-context"
import {
  FileText, MessageSquare, BookOpen, Settings,
  Moon, Sun, LogOut, ChevronUp, Network, Upload, Workflow,
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

export function AppSidebar() {
  const router = useRouter()
  const pathname = usePathname()
  const user = useUser()
  const { dark, toggleDark } = useDarkMode()

  async function handleLogout() {
    await apiFetch("/api/auth/logout", { method: "POST" }).catch(() => {})
    router.push("/login")
  }

  return (
    <aside className="w-60 border-r bg-sidebar flex flex-col shrink-0 hidden md:flex">
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
              onClick={() => router.push(item.href)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
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
        {/* Dark mode toggle */}
        <button
          onClick={toggleDark}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground transition-colors"
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {dark ? "浅色模式" : "深色模式"}
        </button>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger render={
            <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground transition-colors" />
          }>
              <div className="h-6 w-6 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-medium shrink-0">
                {user.username.charAt(0).toUpperCase()}
              </div>
              <span className="flex-1 text-left truncate">{user.username}</span>
              <ChevronUp className="h-3 w-3 opacity-50" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top">
            <DropdownMenuItem onClick={() => router.push("/settings")}>
              <Settings className="h-4 w-4 mr-2" /> 账户设置
            </DropdownMenuItem>
            <DropdownMenuItem className="text-red-500" onClick={handleLogout}>
              <LogOut className="h-4 w-4 mr-2" /> 退出登录
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  )
}
