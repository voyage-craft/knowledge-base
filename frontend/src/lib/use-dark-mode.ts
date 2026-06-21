"use client"

import { useState, useEffect, useCallback } from "react"

export function useDarkMode() {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return false
    const saved = localStorage.getItem("dark-mode")
    if (saved !== null) return saved === "true"
    return document.documentElement.classList.contains("dark")
  })

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const toggleDark = useCallback(() => {
    setDark((prev) => {
      const next = !prev
      localStorage.setItem("dark-mode", String(next))
      document.documentElement.classList.toggle("dark", next)
      return next
    })
  }, [])

  return { dark, toggleDark }
}
