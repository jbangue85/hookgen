import Link from 'next/link';
import { Layers } from 'lucide-react';

export default function Navbar() {
  return (
    <nav className="fixed w-full z-50 top-0 transition-all duration-300 bg-white/60 backdrop-blur-md border-b border-white/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-center items-center h-20">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-brand-primary to-brand-accent flex items-center justify-center text-white shadow-lg shadow-brand-accent/20">
              <Layers size={20} />
            </div>
            <Link href="/" className="text-2xl font-bold tracking-tight text-brand-text">
              AdClip<span className="text-brand-accent">.AI</span>
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
