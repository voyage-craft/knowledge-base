"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { apiTry } from "@/lib/api-client"
import { toast } from "sonner"
import {
  Plus, Loader2, Shield, ShieldOff, UserCheck, UserX, KeyRound,
} from "lucide-react"

interface AdminUser {
  id: number
  username: string
  email: string
  is_active: boolean
  is_admin: boolean
  created_at: string
  updated_at: string
}

export function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState("")

  // Create user form
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState("")
  const [newEmail, setNewEmail] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [newIsAdmin, setNewIsAdmin] = useState(false)
  const [creating, setCreating] = useState(false)

  // Reset password
  const [resetUserId, setResetUserId] = useState<number | null>(null)
  const [resetPassword, setResetPassword] = useState("")
  const [resetting, setResetting] = useState(false)

  useEffect(() => { fetchUsers() }, [])

  async function fetchUsers() {
    setLoading(true)
    const params = search ? `?search=${encodeURIComponent(search)}` : ""
    const [data] = await apiTry<{ users: AdminUser[]; total: number }>(`/api/admin/users${params}`)
    if (data) { setUsers(data.users); setTotal(data.total) }
    setLoading(false)
  }

  async function createUser() {
    if (!newUsername.trim() || !newEmail.trim() || newPassword.length < 6) {
      toast.error("请填写完整信息，密码至少 6 位")
      return
    }
    setCreating(true)
    const [data, err] = await apiTry<AdminUser>("/api/admin/users", {
      method: "POST",
      body: JSON.stringify({
        username: newUsername.trim(),
        email: newEmail.trim(),
        password: newPassword,
        is_admin: newIsAdmin,
      }),
    })
    if (data) {
      toast.success(`用户 ${data.username} 已创建`)
      setShowCreate(false)
      setNewUsername(""); setNewEmail(""); setNewPassword(""); setNewIsAdmin(false)
      fetchUsers()
    } else {
      toast.error(err?.message || "创建失败")
    }
    setCreating(false)
  }

  async function toggleActive(user: AdminUser) {
    const action = user.is_active ? "禁用" : "启用"
    if (!confirm(`确定要${action}用户 ${user.username} 吗？`)) return
    const [, err] = await apiTry(`/api/admin/users/${user.id}`, {
      method: "PUT",
      body: JSON.stringify({ is_active: !user.is_active }),
    })
    if (!err) { toast.success(`已${action}`); fetchUsers() }
    else toast.error(err.message)
  }

  async function toggleAdmin(user: AdminUser) {
    const action = user.is_admin ? "取消管理员" : "设为管理员"
    if (!confirm(`确定要${action} ${user.username} 吗？`)) return
    const [, err] = await apiTry(`/api/admin/users/${user.id}`, {
      method: "PUT",
      body: JSON.stringify({ is_admin: !user.is_admin }),
    })
    if (!err) { toast.success(`已${action}`); fetchUsers() }
    else toast.error(err.message)
  }

  async function handleResetPassword() {
    if (!resetUserId || resetPassword.length < 6) {
      toast.error("密码至少 6 位")
      return
    }
    setResetting(true)
    const [, err] = await apiTry(`/api/admin/users/${resetUserId}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ new_password: resetPassword }),
    })
    if (!err) {
      toast.success("密码已重置")
      setResetUserId(null)
      setResetPassword("")
    } else {
      toast.error(err.message)
    }
    setResetting(false)
  }

  async function disableUser(user: AdminUser) {
    if (!confirm(`确定要禁用用户 ${user.username} 吗？该用户将无法登录。`)) return
    const [, err] = await apiTry(`/api/admin/users/${user.id}`, { method: "DELETE" })
    if (!err) { toast.success("用户已禁用"); fetchUsers() }
    else toast.error(err.message)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>用户管理</CardTitle>
            <CardDescription>管理系统用户，共 {total} 个用户</CardDescription>
          </div>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
            <Plus className="h-4 w-4 mr-1" /> 新建用户
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search */}
        <div className="flex gap-2">
          <Input
            placeholder="搜索用户名或邮箱..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") fetchUsers() }}
            className="max-w-xs"
          />
          <Button variant="outline" size="sm" onClick={fetchUsers}>搜索</Button>
        </div>

        {/* Create form */}
        {showCreate && (
          <form
            onSubmit={e => { e.preventDefault(); createUser() }}
            className="border rounded-lg p-4 space-y-3 bg-muted/30"
          >
            <h4 className="text-sm font-medium">新建用户</h4>
            <div className="grid grid-cols-3 gap-3">
              <Input placeholder="用户名" value={newUsername} onChange={e => setNewUsername(e.target.value)} />
              <Input placeholder="邮箱" type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} />
              <Input placeholder="密码 (至少6位)" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" checked={newIsAdmin} onChange={e => setNewIsAdmin(e.target.checked)} />
                管理员权限
              </label>
              <Button type="submit" size="sm" disabled={creating}>
                {creating ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                创建
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowCreate(false)}>取消</Button>
            </div>
          </form>
        )}

        {/* User list */}
        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin mr-2" /> 加载中...
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">用户</th>
                  <th className="text-left px-4 py-2 font-medium">邮箱</th>
                  <th className="text-left px-4 py-2 font-medium">状态</th>
                  <th className="text-left px-4 py-2 font-medium">角色</th>
                  <th className="text-right px-4 py-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} className="border-t hover:bg-muted/30">
                    <td className="px-4 py-2.5 font-medium">{u.username}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{u.email}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant={u.is_active ? "default" : "secondary"}>
                        {u.is_active ? "活跃" : "禁用"}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5">
                      {u.is_admin ? (
                        <Badge variant="outline" className="text-blue-500 border-blue-500">管理员</Badge>
                      ) : (
                        <span className="text-muted-foreground">普通用户</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost" size="sm" className="h-7 px-2"
                          onClick={() => toggleActive(u)}
                          title={u.is_active ? "禁用" : "启用"}
                        >
                          {u.is_active
                            ? <UserX className="h-3.5 w-3.5 text-orange-500" />
                            : <UserCheck className="h-3.5 w-3.5 text-green-500" />}
                        </Button>
                        <Button
                          variant="ghost" size="sm" className="h-7 px-2"
                          onClick={() => toggleAdmin(u)}
                          title={u.is_admin ? "取消管理员" : "设为管理员"}
                        >
                          {u.is_admin
                            ? <ShieldOff className="h-3.5 w-3.5 text-blue-500" />
                            : <Shield className="h-3.5 w-3.5 text-muted-foreground" />}
                        </Button>
                        <Button
                          variant="ghost" size="sm" className="h-7 px-2"
                          onClick={() => { setResetUserId(u.id); setResetPassword("") }}
                          title="重置密码"
                        >
                          <KeyRound className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Reset password dialog */}
        {resetUserId !== null && (
          <form
            onSubmit={e => { e.preventDefault(); handleResetPassword() }}
            className="border rounded-lg p-4 space-y-3 bg-yellow-50 dark:bg-yellow-950/20"
          >
            <h4 className="text-sm font-medium">重置密码</h4>
            <div className="flex items-center gap-2">
              <Input
                type="password"
                placeholder="新密码 (至少6位)"
                value={resetPassword}
                onChange={e => setResetPassword(e.target.value)}
                className="max-w-xs"
              />
              <Button type="submit" size="sm" disabled={resetting}>
                {resetting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                确认重置
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setResetUserId(null)}>取消</Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
