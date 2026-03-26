from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from db.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    status = Column(String, default="created")  # created, transcribing, matching, export_ready, exporting, completed, failed
    mode = Column(String, default="AUTO") # AUTO or REVIEW
    audio_file_path = Column(String, nullable=True)
    audio_duration = Column(Float, nullable=True)
    audio_tone = Column(String, nullable=True)
    audio_transcript = Column(String, nullable=True)
    exported_video_path = Column(String, nullable=True)
    product_image_path = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    speech_phrases = Column(JSON, nullable=True)  # Phrase boundaries from speech rhythm analysis

    # One to many
    audio_keywords = relationship("AudioKeyword", back_populates="project", cascade="all, delete")
    video_files = relationship("VideoFile", back_populates="project", cascade="all, delete")
    selected_clips = relationship("SelectedClip", back_populates="project", cascade="all, delete", order_by="SelectedClip.order")

class AudioKeyword(Base):
    __tablename__ = "audio_keywords"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"))
    word = Column(String, index=True)
    timestamp_start = Column(Float)
    timestamp_end = Column(Float)
    
    project = relationship("Project", back_populates="audio_keywords")

class VideoFile(Base):
    __tablename__ = "video_files"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"))
    file_path = Column(String)
    file_hash = Column(String, index=True) # SHA-256 for caching
    status = Column(String, default="pending") # pending, analyzing, completed, failed
    
    project = relationship("Project", back_populates="video_files")
    segments = relationship("SegmentAnalysis", back_populates="video_file", cascade="all, delete")

class SegmentAnalysis(Base):
    __tablename__ = "segment_analysis"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    video_file_id = Column(String, ForeignKey("video_files.id"))
    start_sec = Column(Float)
    end_sec = Column(Float)
    description = Column(String)
    mood = Column(String)
    keywords = Column(JSON, default=[]) # List of keywords
    ad_role = Column(String, nullable=True, default="lifestyle")
    score_cache = Column(Float, default=0.0) # Temporary store for matching engine
    
    video_file = relationship("VideoFile", back_populates="segments")

class SelectedClip(Base):
    __tablename__ = "selected_clips"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"))
    segment_id = Column(String, ForeignKey("segment_analysis.id"))
    start_sec = Column(Float)
    end_sec = Column(Float)
    order = Column(Integer)
    approved = Column(Boolean, default=True) # For REVIEW mode
    
    project = relationship("Project", back_populates="selected_clips")
    segment = relationship("SegmentAnalysis")
