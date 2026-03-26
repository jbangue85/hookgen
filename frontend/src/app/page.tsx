"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { UploadCloud, Play, Settings, Wand2, FileAudio, FileVideo, ImagePlus } from 'lucide-react';
import Navbar from '@/components/Navbar';
import { motion } from 'framer-motion';

export default function Home() {
  const router = useRouter();
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [videoFiles, setVideoFiles] = useState<File[]>([]);
  const [productImage, setProductImage] = useState<File | null>(null);
  const [mode, setMode] = useState<'AUTO' | 'REVIEW'>('AUTO');
  const [isUploading, setIsUploading] = useState(false);

  const handleAudioChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setAudioFile(e.target.files[0]);
    }
  };

  const handleVideoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setVideoFiles(Array.from(e.target.files));
    }
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setProductImage(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!audioFile || videoFiles.length === 0) return;
    
    setIsUploading(true);
    const formData = new FormData();
    formData.append('audio', audioFile);
    videoFiles.forEach(vf => formData.append('videos', vf));
    if (productImage) {
      formData.append('product_image', productImage);
    }
    formData.append('mode', mode);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/projects`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.project_id) {
        router.push(`/project/${data.project_id}`);
      }
    } catch (error) {
      console.error(error);
      alert("Failed to upload files.");
      setIsUploading(false);
    }
  };

  return (
    <>
      <Navbar />
      <main className="pt-32 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <span className="inline-block py-1 px-3 rounded-full bg-brand-primary text-white text-xs font-bold tracking-wider mb-6">
              AI-POWERED EDITOR
            </span>
            <h1 className="text-5xl sm:text-6xl font-extrabold tracking-tight text-brand-text mb-6 uppercase">
              Turn Raw Content into <br className="hidden sm:block" />
              <span className="gradient-text">Viral Ads. Instantly.</span>
            </h1>
            <p className="text-lg text-gray-500 max-w-2xl mx-auto">
              Upload your voiceover and B-roll. Our AI analyzes the mood, matches the keywords, and generates a polished 9:16 ad ready for TikTok, Reels, and Facebook Shorts.
            </p>
          </motion.div>
        </div>

        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }} 
          animate={{ opacity: 1, scale: 1 }} 
          transition={{ duration: 0.5, delay: 0.2 }}
          className="glass-card max-w-3xl mx-auto p-8 relative overflow-hidden"
        >
          {/* Decorative glow */}
          <div className="absolute -top-32 -right-32 w-64 h-64 bg-brand-accent/20 blur-3xl rounded-full pointer-events-none"></div>
          
          <form onSubmit={handleSubmit} className="relative z-10 space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Audio Upload */}
              <div className="space-y-3">
                <label className="text-sm font-semibold flex items-center gap-2 text-brand-text">
                  <FileAudio size={16} className="text-brand-accent" />
                  Voiceover Audio
                </label>
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center hover:border-brand-accent hover:bg-brand-accent/5 transition-colors cursor-pointer relative">
                  <input type="file" accept="audio/*" onChange={handleAudioChange} className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" required />
                  <UploadCloud className="mx-auto text-gray-400 mb-2 h-8 w-8" />
                  <p className="text-sm text-gray-600 font-medium">Click or drag audio</p>
                  <p className="text-xs text-gray-400 mt-1 max-w-[200px] mx-auto truncate">
                    {audioFile ? audioFile.name : "MP3, WAV, M4A"}
                  </p>
                </div>
              </div>

              {/* Video Upload */}
              <div className="space-y-3">
                <label className="text-sm font-semibold flex items-center gap-2 text-brand-text">
                  <FileVideo size={16} className="text-brand-accent" />
                  B-Roll Videos
                </label>
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center hover:border-brand-accent hover:bg-brand-accent/5 transition-colors cursor-pointer relative">
                  <input type="file" accept="video/*" multiple onChange={handleVideoChange} className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" required />
                  <UploadCloud className="mx-auto text-gray-400 mb-2 h-8 w-8" />
                  <p className="text-sm text-gray-600 font-medium">Click or drag videos</p>
                  <p className="text-xs text-gray-400 mt-1 max-w-[200px] mx-auto truncate">
                    {videoFiles.length > 0 ? `${videoFiles.length} files selected` : "MP4, MOV (Multiple)"}
                  </p>
                </div>
              </div>

              {/* Product Image Upload */}
              <div className="space-y-3">
                <label className="text-sm font-semibold flex items-center gap-2 text-brand-text">
                  <ImagePlus size={16} className="text-brand-accent" />
                  Product Image (Optional)
                </label>
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center hover:border-brand-accent hover:bg-brand-accent/5 transition-colors cursor-pointer relative">
                  <input type="file" accept="image/*" onChange={handleImageChange} className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" />
                  <UploadCloud className="mx-auto text-gray-400 mb-2 h-8 w-8" />
                  <p className="text-sm text-gray-600 font-medium">Click or drag image</p>
                  <p className="text-xs text-gray-400 mt-1 max-w-[200px] mx-auto truncate">
                    {productImage ? productImage.name : "JPEG, PNG, WEBP"}
                  </p>
                </div>
              </div>
            </div>

            {/* Mode Selection */}
            <div className="space-y-3 pt-4 border-t border-gray-100">
              <label className="text-sm font-semibold flex items-center gap-2 text-brand-text">
                <Settings size={16} className="text-brand-accent" />
                Processing Mode
              </label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setMode('AUTO')}
                  className={`p-4 rounded-xl border ${mode === 'AUTO' ? 'border-brand-accent bg-brand-accent/5 ring-1 ring-brand-accent' : 'border-gray-200 hover:border-brand-accent/50'} text-left transition-all`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Wand2 size={18} className={mode === 'AUTO' ? 'text-brand-accent' : 'text-gray-400'} />
                    <span className="font-semibold text-brand-text text-sm">Auto Pilot</span>
                  </div>
                  <p className="text-xs text-gray-500">Zero-click. AI matches clips and exports final video instantly.</p>
                </button>
                <button
                  type="button"
                  onClick={() => setMode('REVIEW')}
                  className={`p-4 rounded-xl border ${mode === 'REVIEW' ? 'border-brand-accent bg-brand-accent/5 ring-1 ring-brand-accent' : 'border-gray-200 hover:border-brand-accent/50'} text-left transition-all`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Play size={18} className={mode === 'REVIEW' ? 'text-brand-accent' : 'text-gray-400'} />
                    <span className="font-semibold text-brand-text text-sm">Review & Edit</span>
                  </div>
                  <p className="text-xs text-gray-500">AI proposes the timeline. You approve or reorder before export.</p>
                </button>
              </div>
            </div>

            <div className="pt-6">
              <button 
                type="submit" 
                disabled={!audioFile || videoFiles.length === 0 || isUploading}
                className="w-full primary-btn py-4 text-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed group"
              >
                {isUploading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Uploading & Preparing Pipeline...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    Generate Ad Video
                    <Wand2 className="group-hover:translate-x-1 transition-transform" size={20} />
                  </span>
                )}
              </button>
            </div>
          </form>
        </motion.div>
      </main>
    </>
  );
}
