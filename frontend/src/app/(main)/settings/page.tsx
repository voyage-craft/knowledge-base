"use client"

import { useState } from "react"
import { useUser } from "@/lib/user-context"
import { AccountTab } from "@/components/settings/AccountTab"
import { SystemTab } from "@/components/settings/SystemTab"
import { UsersTab } from "@/components/settings/UsersTab"
import { PromptTab } from "@/components/settings/PromptTab"
import { RAGTab } from "@/components/settings/RAGTab"
import { ApiRoutesTab } from "@/components/settings/ApiRoutesTab"
import { User, Server, Users, MessageSquareText, Database, Route } from "lucide-react"

const TABS: { id: string; label: string; icon: typeof User; adminOnly?: boolean }[] = [
  { id: "account", label: "账户", icon: User },
  { id: "system", label: "系统配置", icon: Server, adminOnly: true },
  { id: "prompts", label: "提示词管理", icon: MessageSquareText, adminOnly: true },
  { id: "rag", label: "RAG 检索", icon: Database, adminOnly: true },
  { id: "api-routes", label: "API 路由", icon: Route, adminOnly: true },
  { id: "users", label: "用户管理", icon: Users, adminOnly: true },
]

export default function SettingsPage() {
  const user = useUser()
  const [activeTab, setActiveTab] = useState<string>("account")

  const visibleTabs = TABS.filter(t => !t.adminOnly || user.is_admin)

  return (
    <>
      <header className="border-b px-6 py-4">
        <h1 className="text-lg font-semibold">设置</h1>
        <p className="text-xs text-muted-foreground mt-0.5">管理你的账户和系统配置</p>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Tabs */}
          <div className="flex gap-1 border-b">
            {visibleTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-primary text-primary font-medium"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {activeTab === "account" && <AccountTab />}
          {activeTab === "system" && user.is_admin && <SystemTab />}
          {activeTab === "prompts" && user.is_admin && <PromptTab />}
          {activeTab === "rag" && user.is_admin && <RAGTab />}
          {activeTab === "api-routes" && user.is_admin && <ApiRoutesTab />}
          {activeTab === "users" && user.is_admin && <UsersTab />}
        </div>
      </div>
    </>
  )
}
