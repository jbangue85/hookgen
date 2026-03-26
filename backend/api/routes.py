from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import shutil
import os
from pathlib import Path

from db.database import get_db
from db.models import Project, VideoFile, SelectedClip, SegmentAnalysis
from worker.tasks import transcribe_audio_task, match_clips_task, analyze_video_task

router = APIRouter()
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/projects")
async def create_project(
    mode: str = Form("AUTO"),
    audio: UploadFile = File(...),
    videos: List[UploadFile] = File(...),
    product_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    project = Project(mode=mode)
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Save audio
    audio_path = UPLOAD_DIR / f"{project.id}_{audio.filename}"
    with open(audio_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
    
    project.audio_file_path = str(audio_path)
    
    # Save product reference image (if provided)
    if product_image:
        img_path = UPLOAD_DIR / f"{project.id}_ref_{product_image.filename}"
        with open(img_path, "wb") as buffer:
            shutil.copyfileobj(product_image.file, buffer)
        project.product_image_path = str(img_path)
    
    # Save videos
    for video in videos:
        vid_path = UPLOAD_DIR / f"{project.id}_{video.filename}"
        with open(vid_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
            
        # Simplified hash for demonstration (in prod, use actual hashlib stream reading)
        vid_hash = str(vid_path) + "_hash" 
        vid_file = VideoFile(
            project_id=project.id,
            file_path=str(vid_path),
            file_hash=vid_hash
        )
        db.add(vid_file)
        
    db.commit()

    # Trigger pipeline
    project.status = "transcribing"
    db.commit()
    
    # Start chain: Async task
    transcribe_audio_task.delay(project.id)
    
    return {"project_id": project.id, "status": "started"}

@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return {
        "id": project.id,
        "status": project.status,
        "mode": project.mode,
        "exported_video_path": project.exported_video_path,
        "error_message": project.error_message
    }

@router.get("/projects/{project_id}/clips")
def get_project_clips(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404)
        
    clips = []
    for sc in project.selected_clips:
        clips.append({
            "id": sc.id,
            "order": sc.order,
            "approved": sc.approved,
            "segment": {
                "id": sc.segment.id,
                "description": sc.segment.description,
                "mood": sc.segment.mood,
                "keywords": sc.segment.keywords,
                "start_sec": sc.segment.start_sec,
                "end_sec": sc.segment.end_sec
            }
        })
    return {"clips": clips}

@router.post("/projects/{project_id}/export")
def trigger_export(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404)
        
    if project.status != "export_ready" and project.mode == "REVIEW":
        raise HTTPException(status_code=400, detail="Not ready for export")
        
    project.status = "exporting"
    db.commit()
    
    from worker.tasks import export_video_task
    export_video_task.delay(project.id)
    return {"status": "exporting"}

@router.get("/projects/{project_id}/download")
def download_project_video(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.exported_video_path:
        raise HTTPException(status_code=404, detail="Video not found")
        
    file_path = Path(project.exported_video_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")
        
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=f"adclip_{project_id}.mp4",
        content_disposition_type="inline"
    )

@router.post("/projects/{project_id}/reprocess")
def reprocess_project(project_id: str, db: Session = Depends(get_db)):
    """Re-run match + export using existing video analyses. No re-upload needed."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Clear old selected clips
    db.query(SelectedClip).filter(SelectedClip.project_id == project_id).delete()
    
    # Delete old exported video from disk
    if project.exported_video_path:
        try:
            os.remove(project.exported_video_path)
        except:
            pass
        project.exported_video_path = None
    
    project.status = "matching"
    project.error_message = None
    db.commit()
    
    # Re-run matching (passing empty list as first arg since match_clips_task expects 'results' from group)
    from celery import chain
    chain(match_clips_task.s([], project.id)).apply_async()
    
    return {"status": "reprocessing", "project_id": project_id}

@router.post("/projects/{project_id}/reanalyze")
def reanalyze_project(project_id: str, db: Session = Depends(get_db)):
    """Purge ALL old analysis data and re-run Vision AI + matching + export from scratch."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Clear old selected clips
    db.query(SelectedClip).filter(SelectedClip.project_id == project_id).delete()
    
    # Clear ALL old segment analyses for this project's videos
    video_files = db.query(VideoFile).filter(VideoFile.project_id == project_id).all()
    for vf in video_files:
        db.query(SegmentAnalysis).filter(SegmentAnalysis.video_file_id == vf.id).delete()
    
    # Delete old exported video
    if project.exported_video_path:
        try:
            os.remove(project.exported_video_path)
        except:
            pass
        project.exported_video_path = None
    
    project.status = "analyzing"
    project.error_message = None
    db.commit()
    
    # Re-run the full pipeline: analyze all videos -> match -> export
    from celery import chain
    analyze_tasks = [analyze_video_task.si(project_id, vf.id) for vf in video_files]
    full_pipeline = chain(*analyze_tasks, match_clips_task.si(None, project_id))
    full_pipeline.apply_async()
    
    return {"status": "reanalyzing", "project_id": project_id}
