"use client";

import { useEffect, useState, use } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { Download, Sparkles, Home, Loader2, Play, RefreshCw, Eye } from 'lucide-react';
import Link from 'next/link';

interface Project {
  id: string;
  status: string;
  exported_video_path: string;
}

export default function ResultProject({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [reprocessing, setReprocessing] = useState(false);

  const handleReprocess = async () => {
    setReprocessing(true);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects/${resolvedParams.id}/reprocess`, {
        method: 'POST',
      });
      router.push(`/project/${resolvedParams.id}`);
    } catch (error) {
      console.error(error);
      alert('Failed to reprocess.');
      setReprocessing(false);
    }
  };

  const handleReanalyze = async () => {
    setReprocessing(true);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects/${resolvedParams.id}/reanalyze`, {
        method: 'POST',
      });
      router.push(`/project/${resolvedParams.id}`);
    } catch (error) {
      console.error(error);
      alert('Failed to re-analyze.');
      setReprocessing(false);
    }
  };

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects/${resolvedParams.id}`)
      .then(res => res.json())
      .then(data => {
        setProject(data);
        setLoading(false);
      });
  }, [resolvedParams.id]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-blobs"><Loader2 className="animate-spin text-brand-accent h-10 w-10" /></div>;
  }

  if (!project || project.status !== 'completed') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-blobs p-4 text-center">
        <h2 className="text-2xl font-bold mb-2">Video not ready yet.</h2>
        <p className="text-gray-500 mb-6">Or the project does not exist.</p>
        <Link href={`/project/${resolvedParams.id}`} className="primary-btn">Check Progress</Link>
      </div>
    );
  }

  // Generate public URL for the video (Assuming the backend will serve the data folder statically or handle downloads)
  // For MVP, we point to an API endpoint that serves the file, but we didn't write it. 
  // Let's assume we can fetch it via /api/projects/{id}/download 
  const downloadUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects/${project.id}/download`;

  return (
    <>
      <Navbar />
      <main className="pt-32 pb-24 px-4 max-w-4xl mx-auto flex flex-col md:flex-row gap-12 items-center md:items-start">
        {/* Video Player Mockup */}
        <div className="w-full max-w-[320px] shrink-0">
          {/* Outer iPhone Titanium/Graphite frame */}
          <div className="p-1 rounded-[2.5rem] bg-gradient-to-br from-gray-700 via-gray-900 to-black shadow-2xl shadow-brand-accent/30">
            <div className="relative rounded-[2.3rem] border-[6px] border-black bg-black aspect-[9/16] overflow-hidden">
              {/* iPhone Dynamic Island */}
              <div className="absolute top-2 inset-x-0 h-7 bg-black z-20 rounded-full w-28 mx-auto flex items-center justify-end px-2">
                 <div className="w-3 h-3 rounded-full bg-gray-900/50"></div>
              </div>
            
            {/* The actual video player */}
            <video 
              className="w-full h-full object-cover"
              controls
              autoPlay
              loop
              playsInline
              src={downloadUrl}
            >
              Your browser does not support the video tag.
            </video>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 text-center md:text-left pt-4">
          <span className="inline-flex items-center gap-1.5 py-1 px-3 rounded-full bg-green-100 text-green-700 text-xs font-bold tracking-wider mb-4">
            <Sparkles size={14} /> AD READY TO PUBLISH
          </span>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-brand-text mb-4">
            Your Viral Ad is Here.
          </h1>
          <p className="text-lg text-gray-500 mb-8 max-w-md mx-auto md:mx-0">
            The AI has matched your voiceover perfectly with the selected B-roll clips, formatted for TikTok, Reels, and Facebook.
          </p>

          <div className="flex flex-col gap-3 justify-center md:justify-start">
            <a 
              href={downloadUrl} 
              download 
              className="primary-btn py-4 px-8 text-lg"
            >
              <Download size={20} /> Download MP4
            </a>
            <Link href="/" className="secondary-btn py-4 px-8 text-lg">
              <Home size={20} /> Create Another
            </Link>
            <button
              onClick={handleReprocess}
              disabled={reprocessing}
              className="secondary-btn py-4 px-8 text-lg border-brand-accent/50 text-brand-accent hover:bg-brand-accent/10 disabled:opacity-50"
            >
              {reprocessing ? <Loader2 size={20} className="animate-spin" /> : <RefreshCw size={20} />}
              {reprocessing ? 'Reprocessing...' : 'Reprocess Video'}
            </button>
            <button
              onClick={handleReanalyze}
              disabled={reprocessing}
              className="secondary-btn py-4 px-8 text-lg border-orange-400/50 text-orange-500 hover:bg-orange-50 disabled:opacity-50"
            >
              {reprocessing ? <Loader2 size={20} className="animate-spin" /> : <Eye size={20} />}
              {reprocessing ? 'Re-analyzing...' : 'Re-analyze All'}
            </button>
          </div>
        </div>
      </main>
    </>
  );
}
