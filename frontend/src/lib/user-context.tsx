"use client"

import { createContext, useContext } from "react"

export interface User {
  id: number
  username: string
  email?: string
  is_admin: boolean
}

const UserContext = createContext<User | null>(null)

export function UserProvider({ user, children }: { user: User; children: React.ReactNode }) {
  return <UserContext value={user}>{children}</UserContext>
}

export function useUser(): User {
  const ctx = useContext(UserContext)
  if (!ctx) throw new Error("useUser must be used inside UserProvider")
  return ctx
}
