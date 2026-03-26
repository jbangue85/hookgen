"use client";

import { useEffect, useState, use } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import Navbar from '@/components/Navbar';
import { motion, AnimatePresence } from 'framer-motion';

const STEPS = [
  { id: 'created', label: 'Upload Complete' },
  { id: 'transcribing', label: 'Transcribing Audio' },
  { id: 'analyzing', label: 'Analyzing Videos with Vision AI' },
  { id: 'matching', label: 'Matching Clips to Timeline' },
  { id: 'exporting', label: 'Exporting Final Video' }
];

export default function ProjectProgress({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [status, setStatus] = useState<string>('created');
  const [mode, setMode] = useState<string>('AUTO');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    // Initial fetch
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects/${resolvedParams.id}`)
      .then(res => res.json())
      .then(data => {
        setStatus(data.status);
        setMode(data.mode);
        if (data.status === 'completed') router.push(`/project/${resolvedParams.id}/result`);
        if (data.status === 'export_ready') router.push(`/project/${resolvedParams.id}/review`);
      });

    // WebSocket connection
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
    const ws = new WebSocket(`${wsUrl}/ws/project/${resolvedParams.id}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data.status);
      if (data.status === 'failed') setErrorMessage(data.message);
      
      // Auto navigation
      if (data.status === 'completed') router.push(`/project/${resolvedParams.id}/result`);
      if (data.status === 'export_ready') router.push(`/project/${resolvedParams.id}/review`);
    };

    return () => ws.close();
  }, [resolvedParams.id, router]);

  const getStepStatus = (stepId: string) => {
    const stepIndex = STEPS.findIndex(s => s.id === stepId);
    const currentIndex = STEPS.findIndex(s => s.id === status);
    
    if (status === 'completed' || status === 'export_ready') return 'completed';
    if (status === 'failed') return stepId === status ? 'failed' : 'pending';
    
    // Some steps like analyzing/matching map to specific status
    if (stepIndex < currentIndex) return 'completed';
    if (stepIndex === currentIndex) return 'active';
    return 'pending';
  };

  return (
    <>
      <Navbar />
      <main className="pt-32 pb-16 px-4">
        <div className="max-w-xl mx-auto glass-card p-10">
          <div className="text-center mb-10">
            <h1 className="text-3xl font-extrabold text-brand-text mb-2 tracking-tight">AI at Work</h1>
            <p className="text-brand-text/60">Crafting your video ad asynchronously.</p>
          </div>

          <div className="space-y-6">
            <AnimatePresence>
              {STEPS.map((step) => {
                // If in REVIEW mode, skip exporting step in progress tracker until they approve
                if (mode === 'REVIEW' && step.id === 'exporting' && status !== 'exporting') return null;

                const stepStatus = getStepStatus(step.id);
                
                return (
                  <motion.div 
                    key={step.id} 
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={`flex items-center gap-4 p-4 rounded-xl border transition-all duration-500
                      ${stepStatus === 'active' ? 'border-brand-accent bg-brand-accent/5 ring-1 ring-brand-accent shadow-lg' : 
                        stepStatus === 'completed' ? 'border-brand-primary/20 bg-brand-light' : 'border-transparent opacity-50'}`}
                  >
                    <div className="flex-shrink-0">
                      {stepStatus === 'completed' ? (
                        <CheckCircle2 className="text-brand-primary h-6 w-6" />
                      ) : stepStatus === 'active' ? (
                        <Loader2 className="text-brand-accent h-6 w-6 animate-spin" />
                      ) : (
                        <div className="h-6 w-6 rounded-full border-2 border-brand-primary/20" />
                      )}
                    </div>
                    <span className={`font-medium ${stepStatus === 'active' ? 'text-brand-accent' : 'text-brand-text'}`}>
                      {step.label}
                    </span>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>

          {status === 'failed' && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-8 p-4 bg-red-50 border border-red-200 rounded-xl flex gap-3 text-red-700 items-start">
              <AlertCircle className="shrink-0 mt-0.5" size={18} />
              <div>
                <h4 className="font-semibold">Processing Failed</h4>
                <p className="text-sm mt-1">{errorMessage || 'An unknown error occurred.'}</p>
              </div>
            </motion.div>
          )}

        </div>
      </main>
    </>
  );
}
