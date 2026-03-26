"use client";

import { useEffect, useState, use } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { Check, X, GripVertical, Play, Loader2 } from 'lucide-react';
import { motion, Reorder } from 'framer-motion';

interface Clip {
  id: string;
  order: number;
  approved: boolean;
  segment: {
    id: string;
    description: string;
    keywords: string[];
    start_sec: number;
    end_sec: number;
    mood: string;
  };
}

export default function ReviewProject({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects/${resolvedParams.id}/clips`)
      .then(res => res.json())
      .then(data => {
        setClips(data.clips || []);
        setLoading(false);
      });
  }, [resolvedParams.id]);

  const toggleApproval = (id: string) => {
    setClips(clips.map(c => c.id === id ? { ...c, approved: !c.approved } : c));
  };

  const startExport = async () => {
    setExporting(true);
    // Note: In a real app we would send the updated order and approval status to the backend first.
    // Simplifying this to just trigger the export for MVP based on db initial order.
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects/${resolvedParams.id}/export`, {
        method: 'POST'
      });
      router.push(`/project/${resolvedParams.id}`);
    } catch (e) {
      console.error(e);
      setExporting(false);
    }
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-blobs"><Loader2 className="animate-spin text-brand-accent h-10 w-10" /></div>;
  }

  const duration = clips.filter(c => c.approved).reduce((acc, c) => acc + (c.segment.end_sec - c.segment.start_sec), 0);

  return (
    <>
      <Navbar />
      <main className="pt-32 pb-24 px-4 max-w-5xl mx-auto">
        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-extrabold text-brand-text">Review Timeline</h1>
            <p className="text-brand-text/60 mt-1">AI has matched these clips to your audio. Reorder or discard as needed.</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-brand-text/60 font-medium mb-1">Total Duration</p>
            <p className="text-2xl font-bold text-brand-primary">{duration.toFixed(1)}s</p>
          </div>
        </div>

        <div className="glass-card mt-8 p-4">
          <Reorder.Group axis="y" values={clips} onReorder={setClips} className="space-y-3">
            {clips.map((clip) => (
              <Reorder.Item key={clip.id} value={clip} className={`relative flex items-center gap-4 p-4 rounded-xl border transition-colors ${clip.approved ? 'bg-white border-gray-100 hover:border-brand-accent/30 shadow-sm' : 'bg-gray-50 border-transparent opacity-60'}`}>
                <div className="cursor-grab active:cursor-grabbing text-gray-400 p-2 hover:text-brand-accent transition-colors">
                  <GripVertical size={20} />
                </div>
                
                {/* Thumbnail placeholder */}
                <div className="w-24 h-32 bg-gray-200 rounded-lg flex-shrink-0 overflow-hidden relative group">
                  <div className="absolute inset-0 bg-brand-primary/10 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <Play className="text-white fill-current" size={24} />
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-semibold text-brand-text truncate">{clip.segment.description || 'Action sequence'}</h3>
                    <span className="text-xs font-bold px-2 py-1 rounded bg-brand-light text-brand-primary">
                      {(clip.segment.end_sec - clip.segment.start_sec).toFixed(1)}s
                    </span>
                  </div>
                  <div className="flex gap-2 mb-3">
                    <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded-full bg-brand-accent/10 text-brand-accent">
                      {clip.segment.mood || 'Energetic'}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {clip.segment.keywords.slice(0, 3).map(kw => (
                      <span key={kw} className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">#{kw}</span>
                    ))}
                  </div>
                </div>

                <div className="pl-4">
                  <button 
                    onClick={() => toggleApproval(clip.id)}
                    className={`p-3 rounded-full transition-all ${clip.approved ? 'bg-red-50 text-red-500 hover:bg-red-100' : 'bg-green-50 text-green-600 hover:bg-green-100'}`}
                  >
                    {clip.approved ? <X size={20} /> : <Check size={20} />}
                  </button>
                </div>
              </Reorder.Item>
            ))}
          </Reorder.Group>
        </div>
      </main>

      {/* Floating Actions Bar */}
      <div className="fixed bottom-0 left-0 right-0 p-4 border-t border-white/40 bg-white/80 backdrop-blur-md z-40">
        <div className="max-w-5xl mx-auto flex justify-end gap-4">
          <button className="secondary-btn">Cancel</button>
          <button onClick={startExport} disabled={exporting} className="primary-btn px-8">
            {exporting ? <Loader2 className="animate-spin" size={20} /> : 'Generate Final Video'}
          </button>
        </div>
      </div>
    </>
  );
}
