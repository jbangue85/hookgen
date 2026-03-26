import os
import requests
from celery import Celery, chain, group
from core.config import settings
from db.database import SessionLocal
from db.models import Project, VideoFile, AudioKeyword, SegmentAnalysis, SelectedClip
from services.ai_services import transcribe_audio_whisper, analyze_audio_aida, analyze_speech_rhythm, generate_phrase_visual_directions
from services.ffmpeg_utils import extract_frames, cut_clip, process_and_crop_clip_9x16, concatenate_clips_and_mux_audio
from services.matching import select_best_clips

celery_app = Celery("adclip_worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json", timezone="UTC", enable_utc=True)

def notify_frontend(project_id: str, status: str, message: str):
    try:
        requests.post(
            "http://backend:8000/api/internal/ws_broadcast",
            json={"project_id": project_id, "status": status, "message": message},
            timeout=2
        )
    except Exception:
        pass # Ignore connection errors from worker to api

@celery_app.task(bind=True)
def transcribe_audio_task(self, project_id: str):
    notify_frontend(project_id, "transcribing", "Transcribing audio...")
    db = SessionLocal()
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        db.close()
        return

    try:
        result = transcribe_audio_whisper(project.audio_file_path)
        project.audio_duration = result["duration_seconds"]
        project.audio_tone = result["tone"]
        project.audio_transcript = result["text"]
        
        for kw in result["keywords"]:
            db.add(AudioKeyword(
                project_id=project.id,
                word=kw["word"],
                timestamp_start=kw["timestamp_start"],
                timestamp_end=kw["timestamp_end"]
            ))

        # Analyze speech rhythm and store phrase boundaries
        phrases = analyze_speech_rhythm(result["all_words"], result["duration_seconds"])
        project.speech_phrases = phrases

        db.commit()
    except Exception as e:
        project.status = "failed"
        project.error_message = str(e)
        db.commit()
        notify_frontend(project_id, "failed", str(e))
        db.close()
        return

    # Trigger video analysis — SEQUENTIAL to avoid OpenAI rate limits
    video_files = db.query(VideoFile).filter(VideoFile.project_id == project_id).all()
    # Use si() (immutable) so previous task results don't interfere with arguments
    analyze_tasks = [analyze_video_task.si(project_id, vf.id) for vf in video_files]
    full_pipeline = chain(*analyze_tasks, match_clips_task.si(None, project_id))
    full_pipeline.apply_async()
    db.close()

@celery_app.task(bind=True)
def analyze_video_task(self, project_id: str, video_file_id: str):
    db = SessionLocal()
    video_file = db.query(VideoFile).filter(VideoFile.id == video_file_id).first()
    project = db.query(Project).filter(Project.id == project_id).first()
    if not video_file or not project:
        db.close()
        return
        
    notify_frontend(project_id, "analyzing", f"Analyzing video {video_file.id}...")
    try:
        from services.ai_services import analyze_video_gemini
        
        segments = analyze_video_gemini(video_file.file_path, project.product_image_path)
        
        for seg in segments:
            # Store contains_reference_product in ad_role field ("product" or "lifestyle")
            has_product = seg.get("contains_reference_product", False)
            db.add(SegmentAnalysis(
                video_file_id=video_file.id,
                start_sec=float(seg.get("start_sec", 0.0)),
                end_sec=float(seg.get("end_sec", 3.0)),
                description=seg.get("description", ""),
                mood=seg.get("mood", ""),
                keywords=seg.get("keywords", []),
                ad_role="product" if has_product else "lifestyle"
            ))
        db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Task failed: {e}")
    finally:
        db.close()

@celery_app.task(bind=True)
def match_clips_task(self, results, project_id: str):
    import logging
    logger = logging.getLogger(__name__)
    
    notify_frontend(project_id, "matching", "Matching clips...")
    db = SessionLocal()
    project = db.query(Project).filter(Project.id == project_id).first()
    try:
        segments = []
        total_segs = 0
        skipped_segs = 0
        for vf in project.video_files:
            for seg in vf.segments:
                total_segs += 1
                # Skip broken segments (Failed to parse or empty)
                if not seg.description or seg.description == "Failed to parse":
                    skipped_segs += 1
                    continue
                segments.append({
                    "id": seg.id,
                    "video_id": vf.id,
                    "start_sec": seg.start_sec,
                    "end_sec": seg.end_sec,
                    "keywords": seg.keywords or [],
                    "mood": seg.mood or "",
                    "description": seg.description,
                    "ad_role": getattr(seg, "ad_role", "lifestyle"),
                    "contains_reference_product": getattr(seg, "ad_role", "") == "product",
                })

        logger.warning(f"[MATCH] Project {project_id}: {total_segs} total segments, {skipped_segs} skipped (broken), {len(segments)} usable")

        # Split long segments (>5s) into sub-clips of ~3s so we have granular B-roll options.
        # Gemini often returns 1-2 large "scenes" for videos without hard cuts.
        MAX_SEGMENT_DURATION = 5.0
        SUB_CLIP_DURATION = 3.0
        expanded_segments = []
        for seg in segments:
            duration = seg["end_sec"] - seg["start_sec"]
            if duration > MAX_SEGMENT_DURATION:
                # Split into ~3s sub-clips, all inheriting the same description/mood
                num_chunks = max(2, int(duration / SUB_CLIP_DURATION))
                chunk_dur = duration / num_chunks
                for i in range(num_chunks):
                    sub = dict(seg)
                    sub["start_sec"] = round(seg["start_sec"] + i * chunk_dur, 3)
                    sub["end_sec"] = round(seg["start_sec"] + (i + 1) * chunk_dur, 3)
                    expanded_segments.append(sub)
            else:
                expanded_segments.append(seg)

        logger.warning(f"[MATCH] After splitting long segments: {len(expanded_segments)} usable clips (was {len(segments)})")
        segments = expanded_segments

        for i, seg in enumerate(segments):
            logger.warning(f"[MATCH]   Segment {i}: [{seg['start_sec']:.1f}-{seg['end_sec']:.1f}s] mood={seg['mood']}, desc={seg['description'][:60]}...")

        # Step 1: Identify AIDA phases in the audio
        notify_frontend(project_id, "matching", "Analyzing narrative structure (AIDA)...")
        transcript_text = project.audio_transcript or ""
        logger.warning(f"[MATCH] Transcript: {transcript_text[:100]}...")
        aida_phases = analyze_audio_aida(transcript_text, project.audio_duration)
        for phase in aida_phases:
            logger.warning(f"[MATCH]   AIDA: {phase.get('phase','?')} [{phase.get('start_sec',0)}-{phase.get('end_sec',0)}s]: {phase.get('visual_direction','?')}")

        # Step 2: Load speech phrases and generate visual directions per phrase
        notify_frontend(project_id, "matching", "Generating visual directions per phrase...")
        phrases = project.speech_phrases
        if not phrases:
            # Fallback for old projects: generate phrases now
            logger.warning("[MATCH] No stored speech phrases, generating from transcript...")
            from services.ai_services import analyze_speech_rhythm
            # We don't have all_words stored, so create uniform phrases as fallback
            num_phrases = max(1, int(project.audio_duration / 3.0))
            phrase_dur = project.audio_duration / num_phrases
            phrases = []
            for i in range(num_phrases):
                phrases.append({
                    "text": "",
                    "start_sec": round(i * phrase_dur, 2),
                    "end_sec": round((i + 1) * phrase_dur, 2),
                    "duration": round(phrase_dur, 2),
                })

        # Enrich phrases with visual descriptions using GPT
        enriched_phrases = generate_phrase_visual_directions(phrases, aida_phases, transcript_text)
        for i, p in enumerate(enriched_phrases):
            logger.warning(f"[MATCH]   Phrase {i} [{p.get('start_sec',0):.1f}-{p.get('end_sec',0):.1f}s] ({p.get('aida_phase','?')}): {p.get('visual_description','?')[:80]}...")

        # Step 3: Match phrases to segments
        notify_frontend(project_id, "matching", "Creating intelligent timeline...")
        selected_clips = select_best_clips(segments, enriched_phrases, aida_phases, project.audio_duration)
        logger.warning(f"[MATCH] Director selected {len(selected_clips)} clips")
        for clip in selected_clips:
            logger.warning(f"[MATCH]   Cut #{clip.get('order',0)}: seg_id={clip.get('id','?')}, {clip.get('start_sec',0)}-{clip.get('end_sec',0)}s (dur={clip.get('end_sec',0)-clip.get('start_sec',0):.1f}s)")
        
        for clip in selected_clips:
            db.add(SelectedClip(
                project_id=project.id,
                segment_id=clip["id"],
                start_sec=clip["start_sec"],
                end_sec=clip["end_sec"],
                order=clip["order"]
            ))
            
        if project.mode == "AUTO":
            project.status = "exporting"
            db.commit()
            export_video_task.delay(project.id)
        else:
            project.status = "export_ready"
            db.commit()
            notify_frontend(project_id, "export_ready", "Ready for review")
            
    except Exception as e:
        project.status = "failed"
        project.error_message = str(e)
        db.commit()
        notify_frontend(project_id, "failed", str(e))
    finally:
        db.close()

@celery_app.task(bind=True)
def export_video_task(self, project_id: str):
    notify_frontend(project_id, "exporting", "Exporting video...")
    db = SessionLocal()
    project = db.query(Project).filter(Project.id == project_id).first()
    
    try:
        clips_to_process = []
        for sc in project.selected_clips:
            if not sc.approved:
                continue
            seg = sc.segment
            vf = seg.video_file
            
            # Create a cropped clip
            out_clip = f"data/{sc.id}_cropped.mp4"
            # Cut first
            raw_cut = f"data/{sc.id}_cut.mp4"
            cut_clip(vf.file_path, sc.start_sec, sc.end_sec, raw_cut)
            # Crop 9:16
            process_and_crop_clip_9x16(raw_cut, out_clip)
            clips_to_process.append(out_clip)
            
            # Clean intermediate
            try:
                os.remove(raw_cut)
            except: pass
            
        if not clips_to_process:
            raise ValueError("No approved video clips available to export. Ensure video analysis succeeded and clips were matched.")
            
        final_video_path = f"data/export_{project_id}.mp4"
        concatenate_clips_and_mux_audio(clips_to_process, project.audio_file_path, final_video_path)
        
        project.exported_video_path = final_video_path
        project.status = "completed"
        db.commit()
        notify_frontend(project_id, "completed", "Export completed")
    except Exception as e:
        project.status = "failed"
        project.error_message = str(e)
        db.commit()
        notify_frontend(project_id, "failed", str(e))
    finally:
        try:
            for tmp_clip in clips_to_process:
                os.remove(tmp_clip)
        except: pass
        db.close()
