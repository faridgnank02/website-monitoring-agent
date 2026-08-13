"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { Activity, LayoutDashboard, Globe, LogOut } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/sites", label: "Sites", icon: Globe },
  { href: "/activity", label: "Activity", icon: Activity },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [email, setEmail] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) router.replace("/login");
    else setEmail(localStorage.getItem("email") || "");
  }, [router]);

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    router.replace("/login");
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-56 flex flex-col border-r border-border">
        {/* Brand */}
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center shrink-0">
            <span className="text-primary-foreground text-xs font-bold">M</span>
          </div>
          <span className="font-semibold text-sm text-foreground">Monitor Agent</span>
        </div>

        <Separator />

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                pathname === href
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          ))}
        </nav>

        <Separator />

        {/* User footer */}
        <div className="px-3 py-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground truncate max-w-[130px]">{email}</span>
          <button
            onClick={logout}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
