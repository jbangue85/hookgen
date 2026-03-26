import os
import subprocess
import json
import uuid
import math
from pathlib import Path

# Base output directory
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def run_ffmpeg(cmd):
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg command failed: {' '.join(cmd)}\nError: {e.stderr}")

def get_video_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0

def extract_frames(video_path: str, interval: int = 2) -> list[dict]:
    """
    Extracts frames every `interval` seconds and saves them as JPEG (q=70).
    Returns a list of dicts with frame info: [{'timestamp': float, 'path': str}, ...]
    """
    video_id = Path(video_path).stem
    frames_dir = OUTPUT_DIR / f"{video_id}_frames"
    frames_dir.mkdir(exist_ok=True)
    
    # Extract 1 frame every interval seconds. qscale:v=5 corresponds to ~70 quality for JPEG
    cmd = [
        "ffmpeg", "-i", video_path, "-vf", f"fps=1/{interval}",
        "-qscale:v", "5", f"{frames_dir}/frame_%04d.jpg", "-y"
    ]
    run_ffmpeg(cmd)
    
    frames = []
    # Identify generated frames and assign timestamps
    for file in sorted(frames_dir.glob("frame_*.jpg")):
        # We named them output_%04d.jpg, so we can calculate timestamp
        idx_str = file.stem.split("_")[1]
        idx = int(idx_str) - 1
        timestamp = idx * interval
        frames.append({"timestamp": timestamp, "path": str(file)})
        
    return frames

def cut_clip(video_path: str, start_sec: float, end_sec: float, output_path: str):
    """Cuts a clip from a video based on timestamps without re-encoding."""
    # Note: For frame accurate cuts, we re-encode if we need exact cuts.
    # Given requirements say exact timestamps, we should reencode the cut snippet.
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_sec), "-to", str(end_sec),
        "-i", video_path, "-c:v", "libx264", "-c:a", "aac", output_path
    ]
    run_ffmpeg(cmd)

def process_and_crop_clip_9x16(video_path: str, output_path: str):
    """
    Takes a video and crops/scales to 1080x1920 (9:16).
    If landscape, it adds blurred borders.
    """
    # Using complex filter for blurred background effect
    # 1. Scale input to 1080 width, maintaining AR
    # 2. Scale input to background size, crop, blur
    # 3. Overlay scaled input over blurred background
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[scaled];"
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=luma_radius=min(h\\,w)/20:luma_power=1:chroma_radius=min(cw\\,ch)/20:chroma_power=1[blurred];"
        "[blurred][scaled]overlay=(W-w)/2:(H-h)/2[out]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264", "-c:a", "aac",
        "-b:v", "4000k", "-maxrate", "4000k", "-bufsize", "8000k",
        "-r", "30", output_path
    ]
    run_ffmpeg(cmd)

def extract_audio(video_path: str, output_path: str):
    """Extracts audio to mp3 or wav."""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-q:a", "0", "-map", "a", output_path
    ]
    run_ffmpeg(cmd)

def concatenate_clips_and_mux_audio(clip_paths: list[str], audio_path: str, output_path: str):
    """Concatenates pre-processed 9:16 selected clips and muxes with the original audio."""
    list_file_path = OUTPUT_DIR / f"{uuid.uuid4()}_concat_list.txt"
    with open(list_file_path, "w") as f:
        for clip in clip_paths:
            # Format requires absolute path or relative path, wrapping in single quotes
            # Handle quotes inside path if any
            f.write(f"file '{Path(clip).absolute()}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file_path),
        "-i", audio_path,
        "-c:v", "copy", # Copy since they are all exactly 1080x1920 and encoded identically
        "-c:a", "aac",
        "-map", "0:v:0", # Use video from clips
        "-map", "1:a:0", # Use audio from original audio track
        "-shortest", # End when shortest stream ends (usually the audio)
        # Output limits
        "-fs", "4000M", # Max 4GB per requirement, though 500M is TikTok. Will stick to ~4GB limit max here
        output_path
    ]
    run_ffmpeg(cmd)
    
    # Cleanup list file
    list_file_path.unlink(missing_ok=True)
