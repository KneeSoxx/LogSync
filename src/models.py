"""Pydantic models for LogSync."""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """Normalized log entry from any source."""
    timestamp: datetime = Field(..., description="Parsed timestamp")
    source: str = Field(..., description="Log source/service name")
    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR, etc.)")
    message: str = Field(..., description="Log message content")
    raw_line: Optional[str] = Field(None, description="Original raw log line")
    original_file: Optional[str] = Field(None, description="Source file path")


class LogFile(BaseModel):
    """Uploaded log file metadata."""
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    filepath: str = Field(..., description="Full path to stored file")
    size_bytes: int = Field(..., description="File size in bytes")
    detected_format: Optional[str] = Field(None, description="Auto-detected format")
    custom_parser: Optional[str] = Field(None, description="Custom parser name if used")
    line_count: int = Field(0, description="Number of log lines")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LogStream(BaseModel):
    """A unified stream of logs from multiple files."""
    id: str = Field(..., description="Unique stream identifier")
    name: str = Field(..., description="Stream name (user-defined)")
    source_files: List[str] = Field(default_factory=list, description="List of file IDs in this stream")
    combined_line_count: int = Field(0, description="Total lines across all files")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ParserDefinition(BaseModel):
    """Custom parser definition."""
    name: str = Field(..., description="Unique parser identifier")
    pattern: str = Field(..., description="Regex pattern to match log lines")
    timestamp_pattern: Optional[str] = Field(None, description="Timestamp extraction regex")
    timestamp_format: str = Field(..., description="Date format string (e.g., %Y-%m-%d %H:%M:%S)")
    field_mappings: Dict[str, str] = Field(default_factory=dict, description="Match groups to field names mapping")
    source_field: str = Field(default="source", description="Field containing source name")
    level_field: str = Field(default="level", description="Field containing log level")
    message_field: str = Field(default="message", description="Field containing message")
    builtin: bool = Field(False, description="Whether this is a built-in parser")


class ParserRegistry(BaseModel):
    """Available parsers configuration."""
    custom_parsers: List[ParserDefinition] = Field(default_factory=list)
    auto_detect_order: List[str] = Field(
        default=["json", "syslog", "apache", "python_log", "windows_event"],
        description="Priority order for auto-detection"
    )


def get_registry():
    """Get the global parser registry instance."""
    return ParserRegistry(config_path=None)  # Lazy initialization


def reset_registry(config_path: Optional[Path] = None):
    """Reset and reload the parser registry."""
    global parser_registry
    if config_path:
        parser_registry = ParserRegistry(config_path=config_path)
    else:
        parser_registry = ParserRegistry()
