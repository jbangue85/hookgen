"use client";

import { useEffect, useState } from 'react';
import Navbar from '@/components/Navbar';
import Link from 'next/link';
import { Play, Clock, Film } from 'lucide-react';
import { motion } from 'framer-motion';

export default function ProjectsHistory() {
  const [projects, setProjects] = useState([]);
  
  // Fetch from an endpoint we haven't built yet, but we will mock it or add it later if required.
  // For the sake of UI completeness:
  useEffect(() => {
    // In a real app this would fetch the list. Since I didn't add the /api/projects GET list route, we show empty state or handle errors gracefully.
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects_list`)
      .then(res => res.json())
      .then(data => setProjects(data.projects || []))
      .catch(() => setProjects([]));
  }, []);

  return (
    <>
      <Navbar />
      <main className="pt-32 pb-24 px-4 max-w-5xl mx-auto">
        <div className="mb-10 text-center sm:text-left">
          <h1 className="text-4xl font-extrabold text-brand-text mb-2">My Projects</h1>
          <p className="text-gray-500 text-lg">All your AI-generated video ads in one place.</p>
        </div>

        {projects.length === 0 ? (
          <div className="glass-card p-12 text-center border-dashed border-2 border-gray-200 bg-transparent shadow-none">
            <Film className="mx-auto h-12 w-12 text-gray-300 mb-4" />
            <h3 className="text-xl font-bold text-gray-700 mb-2">No projects yet</h3>
            <p className="text-gray-500 mb-6">Create your first highly converting video ad right now.</p>
            <Link href="/" className="primary-btn mx-auto inline-flex">Start Free Trial</Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((p: any, i) => (
              <motion.div 
                key={p.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className="glass-card p-4 hover:-translate-y-1 transition-transform group"
              >
                <div className="bg-gray-100 aspect-[9/16] rounded-xl mb-4 relative overflow-hidden flex items-center justify-center">
                   <div className="absolute inset-0 bg-brand-primary/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                   <Play className="text-brand-accent h-10 w-10 opacity-50 group-hover:opacity-100 drop-shadow-md transition-opacity" fill="currentColor" />
                </div>
                <div>
                   <h3 className="font-bold text-gray-800 truncate">Project {p.id.substring(0,6)}</h3>
                   <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-1">
                     <Clock size={12} /> {new Date().toLocaleDateString()}
                   </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
