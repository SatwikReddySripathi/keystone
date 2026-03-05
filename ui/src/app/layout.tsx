import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Keystone - Transaction Governance for Agent Actions",
  description: "Preview, approve, canary, contain, prove.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#09090b]">
        <nav className="border-b border-gray-800/60 bg-[#09090b]/90 backdrop-blur-xl sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
            <a href="/" className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">K</div>
              <span className="text-sm font-semibold tracking-tight text-gray-200">Keystone</span>
            </a>
            <div className="flex items-center gap-4">
              <span className="text-[10px] text-gray-600 uppercase tracking-widest">Transaction Governance</span>
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}