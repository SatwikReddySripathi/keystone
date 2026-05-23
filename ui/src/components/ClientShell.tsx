"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Sidebar } from "@/components/Sidebar";

export function ClientShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ShellContent>{children}</ShellContent>
    </AuthProvider>
  );
}

function ShellContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { me, loading } = useAuth();
  const isPublic = pathname === "/login";

  // Not signed in: show just the content (login page handles itself)
  if (isPublic) {
    return <div className="flex-1 overflow-y-auto relative z-10 h-screen">{children}</div>;
  }

  // Signed in but profile not yet loaded: render blank shell rather than flashing the app
  if (loading || !me) {
    return (
      <div className="flex-1 flex items-center justify-center h-screen">
        <div className="text-xs text-ks-text3 font-mono uppercase tracking-widest">
          Signing in…
        </div>
      </div>
    );
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-y-auto relative z-10 p-8 h-screen">{children}</main>
    </>
  );
}
