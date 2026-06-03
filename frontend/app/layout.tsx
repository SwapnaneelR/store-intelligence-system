import type { Metadata } from 'next'
import './globals.css'
import Sidebar from '@/components/layout/Sidebar'

export const metadata: Metadata = {
  title: 'Store Intelligence — Brigade Road',
  description: 'Real-time retail store analytics powered by CCTV tracking',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased">
        <Sidebar />
        <main className="ml-56 min-h-screen flex flex-col">
          {children}
        </main>
      </body>
    </html>
  )
}
