import type { ReactNode } from 'react'
import { cookies } from 'next/headers'

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = (await cookies()).get('sid')?.value
  return (
    <html lang="en">
      <body>
        {session ? <span className="cart">3 items</span> : null}
        {children}
      </body>
    </html>
  )
}
