"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { BookOpen, AlertCircle } from "lucide-react"

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  function extractErrorMessage(data: any): string {
    if (data.message && typeof data.message === "string") {
      return data.message
    }
    if (typeof data.detail === "string") {
      return data.detail
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((e: any) => {
          const field = e.loc?.length > 1 ? e.loc[e.loc.length - 1] : ""
          return field ? `${field}: ${e.msg}` : e.msg
        })
        .join("; ")
    }
    return "登录失败"
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(extractErrorMessage(data))
        return
      }

      router.push("/documents")
    } catch {
      setError("无法连接到服务器")
    } finally {
      setLoading(false)
    }
  }

  function clearError() {
    if (error) setError("")
  }

  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-slate-50 to-indigo-50 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-900">
              <BookOpen className="h-8 w-8 text-blue-600 dark:text-blue-400" />
            </div>
          </div>
          <CardTitle className="text-2xl">知识库</CardTitle>
          <CardDescription>登录你的知识库系统</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">用户名</label>
              <Input
                type="text"
                placeholder="admin"
                value={username}
                onChange={e => { setUsername(e.target.value); clearError() }}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">密码</label>
              <Input
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={e => { setPassword(e.target.value); clearError() }}
                required
              />
            </div>
            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "登录中..." : "登录"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
