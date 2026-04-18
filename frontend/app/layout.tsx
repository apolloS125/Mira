import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mira Dashboard",
  description: "Personal secretary agent — writes its own skills and connects tools via chat.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-6xl px-6 py-8">
          <header className="mb-8 flex items-center justify-between">
            <Link href="/" className="text-2xl font-semibold tracking-tight">
              🧠 Mira
            </Link>
            <span className="text-sm text-neutral-500">เลขาส่วนตัว AI</span>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
