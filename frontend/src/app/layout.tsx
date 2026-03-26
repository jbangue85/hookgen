import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'AdClip AI | Automated Ad Video Editor',
  description: 'Create production-ready video ads for Facebook, TikTok, and Instagram with AI.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} bg-blobs min-h-screen`}>{children}</body>
    </html>
  );
}
