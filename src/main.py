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


# ==================== Correlation API ====================

@app.get("/api/correlate", tags=["Correlation"])
async def correlate_logs(
    window_ms: int = Query(500, description="Time window in milliseconds for correlation")
):
    """
    Find correlated events across all logs.
    
    Groups events that occur within the specified time window (default: 500ms).
    
    - window_ms: Time window for grouping related events
    """
    log_dir = get_temp_log_dir()
    all_events = []
    
    for filepath in log_dir.glob("*.log"):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    parsed = parser_registry.parse_line(line)
                    if parsed and parsed.get('timestamp'):
                        all_events.append({
                            **parsed,
                            'file': filepath.name,
                            'line_number': line_num
                        })
        except Exception:
            continue
    
    # Correlate events
    service = get_correlation_service(window_ms=window_ms)
    groups = service.correlate_events(all_events)
    
    result = []
    for i, group in enumerate(groups):
        if not group:
            continue
        
        # Find the earliest event in the group as reference
        reference = min(group, key=lambda x: x.get('timestamp', ''))
        
        group_entry = {
            'group_id': f"corr_{i}",
            'reference_event': reference,
            'event_count': len(group),
            'time_span_ms': _calculate_group_timespan(group),
            'events': [
                {
                    'timestamp': e['timestamp'],
                    'source': e['source'],
                    'level': e['level'],
                    'message': e['message'][:200] + '...' if len(e['message']) > 200 else e['message'],
                    'file': e.get('file', 'unknown'),
                    'line_number': e.get('line_number', 0)
                }
                for e in group
            ]
        }
        result.append(group_entry)
    
    return {
        'total_groups': len(result),
        'window_ms': window_ms,
        'groups': result
    }


def _calculate_group_timespan(events: List[Dict[str, Any]]) -> float:
    """Calculate time span in milliseconds for a group of events."""
    if not events:
        return 0
    
    timestamps = [datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) if 'Z' in str(e['timestamp']) else datetime.fromisoformat(e['timestamp']) for e in events if e.get('timestamp')]
    if not timestamps:
        return 0
    
    min_time = min(timestamps)
    max_time = max(timestamps)
    
    return (max_time - min_time).total_seconds() * 1000


@app.post("/api/correlate", tags=["Correlation"])
async def correlate_logs_post(
    window_ms: int = Query(500),
    file_ids: List[str] = Query(None)
):
    """
    Correlate events from specific files.
    
    - window_ms: Time window for grouping
    - file_ids: Optional list of file IDs to correlate (if not provided, uses all files)
    """
    log_dir = get_temp_log_dir()
    all_events = []
    
    # Determine which files to process
    if file_ids:
        files_to_process = [f for f in log_dir.glob("*.log") if create_log_file_id() in file_ids or f.name.startswith(file_ids[0])]
    else:
        files_to_process = list(log_dir.glob("*.log"))
    
    for filepath in files_to_process:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    parsed = parser_registry.parse_line(line)
                    if parsed and parsed.get('timestamp'):
                        all_events.append({
                            **parsed,
                            'file': filepath.name,
                            'line_number': line_num
                        })
        except Exception:
            continue
    
    service = get_correlation_service(window_ms=window_ms)
    groups = service.correlate_events(all_events)
    
    result = []
    for i, group in enumerate(groups):
        if not group:
            continue
        
        reference = min(group, key=lambda x: x.get('timestamp', ''))
        
        group_entry = {
            'group_id': f"corr_{i}",
            'reference_event': reference,
            'event_count': len(group),
            'time_span_ms': _calculate_group_timespan(group),
            'events': [
                {
                    'timestamp': e['timestamp'],
                    'source': e['source'],
                    'level': e['level'],
                    'message': e['message'][:200] + '...' if len(e['message']) > 200 else e['message'],
                    'file': e.get('file', 'unknown'),
                    'line_number': e.get('line_number', 0)
                }
                for e in group
            ]
        }
        result.append(group_entry)
    
    return {
        'total_groups': len(result),
        'window_ms': window_ms,
        'files_processed': len(files_to_process),
        'groups': result
    }


# ==================== Enhanced Search API ====================

@app.get("/api/search", tags=["Search"])
async def search_logs(
    query: str = Query("", description="Keywords to search"),
    start: Optional[str] = Query(None, description="Start timestamp (ISO format)"),
    end: Optional[str] = Query(None, description="End timestamp (ISO format)"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    sources: str = Query("", description="Comma-separated list of source names to filter")
):
    """
    Search across all logs with multiple filters.
    
    - query: Keywords to search in message content (optional)
    - start: Filter from this timestamp (ISO format, inclusive)
    - end: Filter until this timestamp (ISO format, inclusive)  
    - level: Filter by log level (e.g., "ERROR", "INFO")
    - sources: Comma-separated list of source names to include
    """
    try:
        services = search_service
        
        filters = {
            'query': query if query else None,
            'start_time': datetime.fromisoformat(start.replace('Z', '+00:00')) if start else None,
            'end_time': datetime.fromisoformat(end.replace('Z', '+00:00')) if end else None,
            'level': level,
            'sources': [s.strip() for s in sources.split(',') if s.strip()] if sources else None
        }
        
        results = services.search(**filters)
        
        return {
            'total': len(results),
            'results': results,
            'stats': services.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Search error: {str(e)}")


@app.post("/api/search/export", tags=["Search"])
async def export_search_results(
    format: str = Query("json", description="Export format (json, csv)"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    level: Optional[str] = Query(None)
):
    """
    Export search results to file format.
    
    - format: json or csv
    - start/end/level: Same filters as /api/search
    
    Returns a download URL for the exported file.
    """
    try:
        from src.storage.file_manager import get_temp_log_dir
        
        # Get results
        services = search_service
        filters = {
            'start_time': datetime.fromisoformat(start.replace('Z', '+00:00')) if start else None,
            'end_time': datetime.fromisoformat(end.replace('Z', '+00:00')) if end else None,
            'level': level
        }
        
        results = services.search(**filters)
        
        # Generate export filename
        import uuid
        export_id = str(uuid.uuid4())[:8]
        export_path = get_temp_log_dir() / f"export_{export_id}.{format}"
        
        # Export to file
        if format == 'csv':
            with open(export_path, 'w', encoding='utf-8') as f:
                # Write CSV header
                f.write('timestamp,source,level,file,line_number,message\n')
                
                for entry in results[:1000]:  # Limit export size
                    ts = entry.get('timestamp', '') or ''
                    source = entry.get('source', '') or ''
                    level = entry.get('level', '') or ''
                    file_name = entry.get('file', '') or ''
                    line_num = entry.get('line_number', 0) or 0
                    message = entry.get('message', '')[:500] or ''
                    
                    # Escape CSV fields
                    message = message.replace('"', '""')
                    f.write(f'"{ts}","{source}","{level}","{file_name}","{line_num}","{message}"\n')
        else:  # JSON
            import json
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'total': len(results),
                    'results': results[:1000]
                }, f, indent=2)
        
        return {
            'export_id': export_id,
            'format': format,
            'file_path': str(export_path),
            'result_count': len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Export error: {str(e)}")
