"""FastAPI application entry point."""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.models import LogEntry, LogFile, ParserDefinition, ParserRegistry, get_registry, reset_registry
from src.storage.file_manager import store_log_file, get_log_file_info, remove_log_file, count_lines, get_temp_log_dir
from src.processors.parser_registry import ParserRegistry


# Initialize FastAPI app
app = FastAPI(
    title="LogSync API",
    description="Multi-format log viewer and correlator API",
    version="0.1.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize parser registry
CONFIG_PATH = Path(__file__).parent.parent / "config" / "logsync_config.json"
parser_registry = ParserRegistry(config_path=CONFIG_PATH)


@app.on_event("startup")
async def startup_event():
    """Create temp directory on startup."""
    get_temp_log_dir()


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "LogSync",
        "version": "0.1.0",
        "endpoints": {
            "docs": "/docs",
            "upload_logs": "/api/logs",
            "list_logs": "/api/logs",
            "search": "/api/search",
            "correlate": "/api/correlate",
            "parsers": "/api/parsers"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ==================== Log File Management ====================

@app.post("/api/logs", tags=["Logs"])
async def upload_logs(files: List[UploadFile] = File(...)):
    """
    Upload one or more log files.
    
    - Accepts multiple files via multipart form
    - Auto-detects format for each file
    - Returns metadata including detected format
    """
    stored_files = []
    
    for file in files:
        try:
            # Store the file
            filepath = store_log_file(await file.read(), file.filename)
            
            # Count lines
            line_count = count_lines(filepath)
            
            # Detect format from first non-empty line
            detected_format = None
            if line_count > 0:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for _ in range(min(5, line_count)):  # Sample first 5 lines
                        line = f.readline().strip()
                        if line:
                            detected_format = parser_registry.detect_format(line)
                            break
            
            # Create log file metadata
            log_file = LogFile(
                id=create_log_file_id(),
                filename=file.filename,
                filepath=str(filepath),
                size_bytes=await file.seek(0, 2),  # Get file size
                line_count=line_count,
                detected_format=detected_format
            )
            
            stored_files.append(log_file)
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing {file.filename}: {str(e)}")
    
    return {"uploaded": len(stored_files), "files": [model.model_dump() for model in stored_files]}


@app.get("/api/logs", tags=["Logs"])
async def list_logs():
    """List all uploaded log files."""
    log_dir = get_temp_log_dir()
    
    if not log_dir.exists():
        return []
    
    logs = []
    for filepath in log_dir.glob("*.log"):
        try:
            file_info = get_log_file_info(filepath)
            
            # Try to detect format again (in case file changed)
            detected_format = None
            if file_info['exists'] and file_info['size_bytes'] > 0:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for _ in range(5):
                        line = f.readline().strip()
                        if line:
                            detected_format = parser_registry.detect_format(line)
                            break
            
            log_entry = LogFile(
                id=create_log_file_id(),  # Generate ID on retrieval
                filename=file_info['filename'],
                filepath=str(filepath),
                size_bytes=file_info['size_bytes'],
                line_count=count_lines(filepath),
                detected_format=detected_format
            )
            logs.append(log_entry)
        except Exception:
            continue
    
    return [log.model_dump() for log in logs]


@app.delete("/api/logs/{file_id}", tags=["Logs"])
async def delete_log(file_id: str):
    """Delete a log file by ID."""
    # Find the file (simplified lookup)
    log_dir = get_temp_log_dir()
    
    for filepath in log_dir.glob("*.log"):
        try:
            if create_log_file_id() == file_id or filepath.name.startswith(file_id):
                removed = remove_log_file(filepath)
                if removed:
                    return {"deleted": True, "file_id": file_id}
                else:
                    return {"deleted": False, "error": "Could not remove file"}
        except Exception:
            continue
    
    return {"deleted": False, "error": "File not found"}


# ==================== Parser Management ====================

@app.get("/api/parsers", tags=["Parsers"])
async def list_parsers():
    """List all available parsers."""
    all_parsers = parser_registry.get_all_parsers()
    
    parsers = []
    for name, parser in all_parsers.items():
        parsers.append({
            "name": name,
            "class_name": parser.__class__.__name__,
            "builtin": getattr(parser, '__module__', '') != ''
        })
    
    return {"parsers": parsers}


@app.post("/api/parsers", tags=["Parsers"])
async def register_parser(parser_def: ParserDefinition):
    """Register a custom parser at runtime."""
    try:
        parser_registry.register(
            name=parser_def.name,
            parser=_create_parser_from_def(parser_def),
            builtin=False
        )
        return {"registered": True, "name": parser_def.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _create_parser_from_def(definition: ParserDefinition) -> BaseParser:
    """Create a dynamic parser from definition."""
    import re
    
    class DynamicParser(BaseParser):
        def __init__(self, pattern, timestamp_format, field_mappings=None, 
                     source_field='source', level_field='level', message_field='message'):
            self.pattern = re.compile(pattern, re.MULTILINE)
            self.timestamp_format = timestamp_format
            self.field_mappings = field_mappings or {}
            self.source_field = source_field
            self.level_field = level_field
            self.message_field = message_field
        
        def can_parse(self, line):
            return bool(self.pattern.match(line.strip()))
        
        def parse(self, line):
            match = self.pattern.match(line.strip())
            if not match:
                return None
            
            groups = match.groupdict()
            
            # Extract timestamp using dateutil
            timestamp = None
            ts_match = re.search(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', line)
            if ts_match:
                try:
                    from dateutil import parser as date_parser
                    timestamp = date_parser.parse(ts_match.group(1))
                except:
                    pass
            
            # Extract level and message
            level = groups.get(self.level_field, 'INFO')
            message = groups.get(self.message_field, '')
            
            return {
                'timestamp': timestamp,
                'source': groups.get(self.source_field, 'unknown'),
                'level': str(level).upper(),
                'message': str(message),
                'raw_line': line
            }
    
    return DynamicParser(
        pattern=definition.pattern,
        timestamp_format=definition.timestamp_format,
        field_mappings=definition.field_mappings,
        source_field=definition.source_field,
        level_field=definition.level_field,
        message_field=definition.message_field
    )


# ==================== Search & Query ====================

@app.get("/api/search", tags=["Search"])
async def search_logs(
    query: str = Query("", description="Search keywords"),
    start: Optional[str] = Query(None, description="Start timestamp (ISO format)"),
    end: Optional[str] = Query(None, description="End timestamp (ISO format)")
):
    """
    Search across all logs.
    
    - query: Keywords to search in message content
    - start: Filter from this timestamp
    - end: Filter until this timestamp
    """
    log_dir = get_temp_log_dir()
    results = []
    
    for filepath in log_dir.glob("*.log"):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Detect parser and parse line
                    parsed = parser_registry.parse_line(line)
                    if not parsed:
                        continue
                    
                    # Apply filters
                    ts = parsed.get('timestamp')
                    
                    # Time range filter
                    if start and ts and datetime.fromisoformat(start) > ts:
                        continue
                    if end and ts and datetime.fromisoformat(end) < ts:
                        continue
                    
                    # Keyword filter
                    if query and query.lower() not in parsed['message'].lower():
                        continue
                    
                    results.append({
                        "file": filepath.name,
                        "line_number": line_num,
                        "timestamp": ts.isoformat() if ts else None,
                        **parsed
                    })
        except Exception:
            continue
    
    return {"total": len(results), "results": results[:100]}  # Limit to 100 results


# ==================== Health & Info ====================

@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("LOGSYNC_PORT", 8000))
    host = os.getenv("LOGSYNC_HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)
