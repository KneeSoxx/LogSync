"""Search service for querying log files."""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path


class SearchService:
    """Service for searching and filtering logs across multiple files."""
    
    def __init__(self):
        self._index = None
    
    @property
    def index(self):
        """Build and return the search index if not already built."""
        if self._index is None:
            self._build_index()
        return self._index
    
    def _build_index(self):
        """Build an inverted index for faster searches."""
        from src.storage.file_manager import get_temp_log_dir
        from src.processors.parser_registry import parser_registry
        
        log_dir = get_temp_log_dir()
        
        # Index: keyword -> [(file, line_num, timestamp, message)]
        self._index = {}
        
        for filepath in log_dir.glob("*.log"):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        parsed = parser_registry.parse_line(line)
                        if not parsed or not parsed.get('timestamp'):
                            continue
                        
                        # Index the message content
                        message_lower = parsed['message'].lower()
                        timestamp_str = str(parsed['timestamp'])
                        
                        for match in re.finditer(r'\b[a-z]{3,}\b', message_lower):
                            word = match.group()
                            if word not in self._index:
                                self._index[word] = []
                            
                            self._index[word].append({
                                'file': filepath.name,
                                'line_number': line_num,
                                'timestamp': timestamp_str,
                                'message': parsed['message'][:200],
                                'source': parsed['source'],
                                'level': parsed['level']
                            })
            except Exception:
                continue
    
    def search(
        self,
        query: str = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        sources: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search logs with various filters.
        
        Args:
            query: Keywords to search in messages
            start_time: Filter from this timestamp (inclusive)
            end_time: Filter until this timestamp (inclusive)
            level: Filter by log level (e.g., "ERROR", "INFO")
            sources: Filter by source names
            
        Returns:
            List of matching log entries with metadata
        """
        results = []
        
        # Use index if query provided, otherwise scan all files
        if query and self._index:
            word_matches = self._index.get(query.lower(), [])
            
            for entry in word_matches:
                if self._filter_entry(entry, start_time, end_time, level, sources):
                    results.append({
                        **entry,
                        'search_score': len(query)  # Simple scoring
                    })
        else:
            # Full scan (useful when using time range only)
            from src.storage.file_manager import get_temp_log_dir
            from src.processors.parser_registry import parser_registry
            
            log_dir = get_temp_log_dir()
            
            for filepath in log_dir.glob("*.log"):
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            
                            parsed = parser_registry.parse_line(line)
                            if not parsed or not parsed.get('timestamp'):
                                continue
                            
                            if self._filter_entry(parsed, start_time, end_time, level, sources):
                                results.append({
                                    **parsed,
                                    'file': filepath.name,
                                    'line_number': line_num,
                                    'search_score': 0
                                })
                except Exception:
                    continue
        
        # Sort by timestamp
        results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return results[:100]  # Limit to 100 results
    
    def _filter_entry(
        self,
        entry: Dict[str, Any],
        start_time: datetime = None,
        end_time: datetime = None,
        level: str = None,
        sources: List[str] = None
    ) -> bool:
        """Apply all filters to a single entry."""
        try:
            ts = entry.get('timestamp')
            if not ts:
                return False
            
            entry_dt = datetime.fromisoformat(ts.replace('Z', '+00:00')) if 'Z' in str(ts) else datetime.fromisoformat(ts)
            
            # Time range filter
            if start_time and entry_dt < start_time:
                return False
            if end_time and entry_dt > end_time:
                return False
            
            # Level filter
            if level and entry.get('level', '').upper() != level.upper():
                return False
            
            # Source filter
            if sources and entry.get('source') not in sources:
                return False
            
            return True
        except (ValueError, TypeError):
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about indexed logs."""
        if not self._index:
            return {
                'total_keywords': 0,
                'indexed_files': 0,
                'total_entries': 0
            }
        
        total_entries = sum(len(entries) for entries in self._index.values())
        
        # Count indexed files (approximate)
        from src.storage.file_manager import get_temp_log_dir
        indexed_files = len(self._index) if self._index else 0
        
        return {
            'total_keywords': len(self._index),
            'indexed_files': indexed_files,
            'total_entries': total_entries
        }


search_service = SearchService()
