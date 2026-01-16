import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app.schemas import ProcessingStatus, VideoProcessingResult

# ========== Testes para Schemas ==========

def test_processing_status_enum():
    """Testa enum de status de processamento"""
    from app.schemas import ProcessingStatus
    
    assert ProcessingStatus.PENDING == "pending"
    assert ProcessingStatus.PROCESSING == "processing"
    assert ProcessingStatus.COMPLETED == "completed"
    assert ProcessingStatus.FAILED == "failed"
    
    # Testa valores
    statuses = list(ProcessingStatus)
    assert len(statuses) == 4
    assert "pending" in statuses
    assert "completed" in statuses

def test_video_processing_result_schema():
    """Testa schema VideoProcessingResult"""
    from app.schemas import VideoProcessingResult
    
    # Teste com sucesso
    result = VideoProcessingResult(
        video_id="test-id",
        status=ProcessingStatus.COMPLETED,
        zip_path="/tmp/test.zip",
        frame_count=10,
        error=None
    )
    
    assert result.video_id == "test-id"
    assert result.status == ProcessingStatus.COMPLETED
    assert result.zip_path == "/tmp/test.zip"
    assert result.frame_count == 10
    assert result.error is None
    
    # Teste com erro
    result_failed = VideoProcessingResult(
        video_id="test-id",
        status=ProcessingStatus.FAILED,
        zip_path=None,
        frame_count=None,
        error="Processing failed"
    )
    
    assert result_failed.status == ProcessingStatus.FAILED
    assert result_failed.error == "Processing failed"