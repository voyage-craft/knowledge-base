import { redirect } from "next/navigation"
import { AppSidebar } from "@/components/AppSidebar"
import { MobileNav } from "@/components/MobileNav"
import { UserProvider } from "@/lib/user-context"
import { authCheck } from "@/lib/auth-client"

export default async function MainLayout({ children }: { children: React.ReactNode }) {
  const user = await authCheck()
  if (!user) redirect("/login")

  return (
    <UserProvider user={user}>
      <div className="flex h-screen overflow-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col min-w-0 overflow-auto">
          {/* Mobile hamburger — only visible on small screens */}
          <MobileNav />
          {children}
        </main>
      </div>
    </UserProvider>
  )
}
