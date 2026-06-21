"use client"

import { useState, FormEvent } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import { Eye, EyeOff } from "lucide-react"
import { apiTry } from "@/lib/api-client"

export function AccountTab() {
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()

    if (newPassword.length < 6) {
      toast.error("新密码至少需要 6 个字符")
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error("两次输入的密码不一致")
      return
    }

    setLoading(true)
    const [, err] = await apiTry("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    })
    if (!err) {
      toast.success("密码修改成功")
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } else {
      toast.error(err.message || "密码修改失败")
    }
    setLoading(false)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>修改密码</CardTitle>
        <CardDescription>输入当前密码和新密码来修改你的账户密码</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
          <div className="space-y-2">
            <label className="text-sm font-medium">当前密码</label>
            <div className="relative">
              <Input
                type={showCurrent ? "text" : "password"}
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                placeholder="输入当前密码"
                required
              />
              <button
                type="button"
                onClick={() => setShowCurrent(!showCurrent)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">新密码</label>
            <div className="relative">
              <Input
                type={showNew ? "text" : "password"}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="至少 6 个字符"
                required
                minLength={6}
              />
              <button
                type="button"
                onClick={() => setShowNew(!showNew)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">确认新密码</label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="再次输入新密码"
              required
            />
          </div>

          <Button type="submit" disabled={loading}>
            {loading ? "提交中..." : "修改密码"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
