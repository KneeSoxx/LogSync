"""File storage and management utilities."""
import os
import tempfile
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional


def get_temp_log_dir() -> Path:
    """Get the temporary directory for storing log files."""
    # Use cross-platform temp directory
    temp_base = Path(os.environ.get("LOGSYNC_LOG_DIR", None) or os.path.expanduser("~/logsync_temp"))
    
    # If not set via env, use system temp
    if not temp_base.exists():
        temp_base = Path(tempfile.gettempdir()) / "logsync"
    
    # Ensure directory exists
    temp_base.mkdir(parents=True, exist_ok=True)
    
    return temp_base


def create_log_file_id() -> str:
    """Generate unique file ID."""
    return str(uuid.uuid4())


def store_log_file(file_content: bytes, filename: str) -> Path:
    """Store uploaded file to temp directory and return its path."""
    from tempfile import gettempdir
    import tempfile
    
    log_dir = Path(gettempdir()) / "logsync"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    base_name = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1] or '.log'
    stored_filename = f"{base_name}_{create_log_file_id()}{ext}"
    
    file_path = log_dir / stored_filename
    
    # Write file with cross-platform line ending normalization
    try:
        content = file_content.decode('utf-8', errors='replace')
        # Normalize line endings (Windows CRLF to Unix LF)
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
    except UnicodeDecodeError:
        # Fallback to latin-1 if UTF-8 fails
        content = file_content.decode('latin-1', errors='replace')
        with open(file_path, 'w', encoding='latin-1', newline='\n') as f:
            f.write(content)
    
    return file_path


def get_log_file_info(filepath: Path) -> dict:
    """Get metadata about a log file."""
    try:
        stat = filepath.stat()
        return {
            'filename': filepath.name,
            'size_bytes': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'exists': True
        }
    except OSError:
        return {
            'filename': filepath.name,
            'exists': False
        }


def remove_log_file(filepath: Path) -> bool:
    """Remove a log file from storage."""
    try:
        filepath.unlink()
        # Clean up empty parent directories
        filepath.parent.rmdir() if not filepath.parent.is_dir() else None
        return True
    except OSError:
        return False


def count_lines(filepath: Path) -> int:
    """Count lines in a log file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except (OSError, IOError):
        return 0
