import { NextResponse } from "next/server"

export async function POST() {
  const res = NextResponse.json({ message: "Logged out" })
  res.cookies.delete("access_token")
  res.cookies.delete("refresh_token")
  return res
}
