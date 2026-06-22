"""Data pipeline module for automated ingestion."""

from app.services.data_pipeline.feedback_processor import FeedbackProcessor
from app.services.data_pipeline.folder_watcher import FolderWatcher
from app.services.data_pipeline.external_fetcher import ExternalFetcher

__all__ = [
    "FeedbackProcessor",
    "FolderWatcher",
    "ExternalFetcher",
]
