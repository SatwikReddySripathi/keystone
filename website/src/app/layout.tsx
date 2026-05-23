import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Keystone — Transaction Governance for AI Agents",
  description:
    "Keystone sits between your AI agents and your production systems. Every action is previewed, policy-checked, canary-executed, and cryptographically audited.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} bg-white text-zinc-900`}>{children}</body>
    </html>
  );
}
