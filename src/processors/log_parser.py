"""Base parser class and built-in log format implementations."""
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any

from dateutil import parser as date_parser


class BaseParser(ABC):
    """Abstract base class for log parsers."""
    
    @abstractmethod
    def can_parse(self, line: str) -> bool:
        """Check if this parser can handle the given log line."""
        pass
    
    @abstractmethod
    def parse(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single log line and return normalized fields."""
        pass


class JSONParser(BaseParser):
    """Parser for JSON formatted logs."""
    
    def can_parse(self, line: str) -> bool:
        try:
            import json
            data = json.loads(line.strip())
            # Check for common log fields
            return any(k in data for k in ['timestamp', 'time', 'level', 'lvl', 'log_level', 'message', 'msg'])
        except (json.JSONDecodeError, ValueError):
            return False
    
    def parse(self, line: str) -> Optional[Dict[str, Any]]:
        import json
        data = json.loads(line.strip())
        
        # Extract timestamp with multiple field names
        ts_field = None
        for field in ['timestamp', 'time', '@timestamp', 'datetime']:
            if field in data and isinstance(data[field], (str, int, float)):
                ts_field = field
                break
        
        # Parse timestamp
        ts_value = data.get(ts_field) or data.get('date') or data.get('created_at')
        timestamp = None
        if ts_value:
            if isinstance(ts_value, datetime):
                timestamp = ts_value
            elif isinstance(ts_value, (int, float)):
                # Unix timestamp
                timestamp = datetime.fromtimestamp(ts_value)
            else:
                try:
                    timestamp = date_parser.parse(str(ts_value))
                except (ValueError, TypeError):
                    pass
        
        # Extract level with multiple field names
        level = data.get('level') or data.get('lvl') or data.get('log_level') or data.get('severity') or 'INFO'
        
        # Extract message with multiple field names  
        message = data.get('message') or data.get('msg') or data.get('text') or data.get('log') or ''
        
        return {
            'timestamp': timestamp,
            'source': data.get('service') or data.get('app') or data.get('logger') or data.get('source') or 'unknown',
            'level': str(level).upper(),
            'message': str(message),
            'raw_line': line
        }


class SyslogParser(BaseParser):
    """Parser for syslog format: Jan 15 10:30:00 hostname process[pid]: message"""
    
    PATTERN = re.compile(
        r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+'  # Timestamp
        r'(\S+)\s+'                                    # Hostname
        r'(\S+?)(?:\[(\d+)\])?:?\s*'                  # Process and optional PID
        r'(.*)$'                                       # Message
    )
    
    MONTHS = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    def can_parse(self, line: str) -> bool:
        return bool(self.PATTERN.match(line.strip()))
    
    def parse(self, line: str) -> Optional[Dict[str, Any]]:
        match = self.PATTERN.match(line.strip())
        if not match:
            return None
        
        ts_str, hostname, process, pid, message = match.groups()
        
        # Parse timestamp (assume current year)
        try:
            month = self.MONTHS.get(ts_str[:3], 1)
            day = int(ts_str[4:6])
            time_parts = ts_str[7:].split(':')
            timestamp = datetime(
                year=datetime.now().year,
                month=month,
                day=day,
                hour=int(time_parts[0]),
                minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
                second=int(time_parts[2]) if len(time_parts) > 2 else 0
            )
        except (ValueError, IndexError):
            return None
        
        # Extract level from message if present
        level = self._extract_level(message) or 'INFO'
        
        return {
            'timestamp': timestamp,
            'source': process + (f'[{pid}]' if pid else ''),
            'level': level.upper(),
            'message': message.strip(),
            'raw_line': line
        }
    
    def _extract_level(self, message: str) -> Optional[str]:
        """Extract log level from syslog message."""
        level_patterns = [
            (r'\bERR\b', 'ERROR'),
            (r'\bWARN(ING)?\b', 'WARNING'),
            (r'\bNOTICE\b', 'NOTICE'),
            (r'\bDEBUG\b', 'DEBUG'),
            (r'\bINFO\b', 'INFO'),
        ]
        for pattern, level in level_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return level
        return None


class ApacheParser(BaseParser):
    """Parser for Apache/Nginx combined log format."""
    
    PATTERN = re.compile(
        r'^(\S+)\s+'                                    # IP address
        r'(\S+)\s+'                                    # Identity
        r'(\S+)\s+'                                    # User
        r'\[([^\]]+)\]\s*'                             # Timestamp
        r'"([^"]*)"\s*'                                # Request
        r'(\d{3})\s+'                                  # Status code
        r'(\d+|-)'                                     # Bytes sent
    )
    
    def can_parse(self, line: str) -> bool:
        return bool(self.PATTERN.match(line.strip()))
    
    def parse(self, line: str) -> Optional[Dict[str, Any]]:
        match = self.PATTERN.match(line.strip())
        if not match:
            return None
        
        ip, identity, user, ts_str, request, status, bytes_sent = match.groups()
        
        # Parse Apache timestamp (e.g., "15/Oct/2024:10:30:00 +0000")
        try:
            timestamp = date_parser.parse(ts_str)
        except (ValueError, TypeError):
            return None
        
        # Determine level from status code
        status_code = int(status)
        if status_code >= 500:
            level = 'ERROR'
        elif status_code >= 400:
            level = 'WARNING'
        else:
            level = 'INFO'
        
        return {
            'timestamp': timestamp,
            'source': 'Apache',
            'level': level,
            'message': f'{request} - {status} - {bytes_sent}',
            'raw_line': line
        }


class PythonLogParser(BaseParser):
    """Parser for Python logging format."""
    
    # Pattern 1: "2024-01-15 10:30:00,123 INFO root: message"
    PATTERN_COMMA = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+'  # Timestamp
        r'(\w+)\s*'                                                # Level
        r'(\S*?)(?::|\s+)'                                        # Logger name
        r'(.*)$'                                                   # Message
    )
    
    # Pattern 2: "2024-01-15 10:30:00 INFO message" (no logger)
    PATTERN_SIMPLE = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+'  # Timestamp
        r'(\w+)\s*'                                                # Level
        r'(.*)$'                                                   # Message
    )
    
    def can_parse(self, line: str) -> bool:
        return bool(self.PATTERN_COMMA.match(line.strip()) or self.PATTERN_SIMPLE.match(line.strip()))
    
    def parse(self, line: str) -> Optional[Dict[str, Any]]:
        # Try comma-separated format first
        match = self.PATTERN_COMMA.match(line.strip())
        if match:
            ts_str, level, logger, message = match.groups()
        else:
            match = self.PATTERN_SIMPLE.match(line.strip())
            if not match:
                return None
            ts_str, level, message = match.groups()
            logger = 'root'
        
        # Parse timestamp
        try:
            timestamp = date_parser.parse(ts_str)
        except (ValueError, TypeError):
            return None
        
        return {
            'timestamp': timestamp,
            'source': logger,
            'level': level.upper(),
            'message': message.strip(),
            'raw_line': line
        }


class WindowsEventParser(BaseParser):
    """Parser for Windows Event Log format variants."""
    
    # Common Windows pattern: "2024-01-15 10:30:00 [Source] - Message"
    PATTERN_V1 = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'  # Timestamp
        r'\[?(\S+)?\]?\s*'                               # Optional source in brackets
        r'(-?)\s*'                                       # Separator
        r'(.*)$'                                         # Message
    )
    
    # Windows variant: "1/15/2024 10:30:00 AM [Source] - Message"
    PATTERN_V2 = re.compile(
        r'^(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM))\s+'  # Timestamp
        r'\[?(\S+)?\]?\s*'                               # Optional source
        r'(-?)\s*'                                       # Separator
        r'(.*)$'                                         # Message
    )
    
    def can_parse(self, line: str) -> bool:
        return bool(self.PATTERN_V1.match(line.strip()) or self.PATTERN_V2.match(line.strip()))
    
    def parse(self, line: str) -> Optional[Dict[str, Any]]:
        # Try pattern 1 (ISO-like)
        match = self.PATTERN_V1.match(line.strip())
        if match:
            ts_str, source, sep, message = match.groups()
            return_value = self._parse_timestamp_v1(ts_str, source, message)
            if return_value:
                return return_value
        
        # Try pattern 2 (US format)
        match = self.PATTERN_V2.match(line.strip())
        if match:
            ts_str, source, sep, message = match.groups()
            return_value = self._parse_timestamp_v2(ts_str, source, message)
            if return_value:
                return return_value
        
        return None
    
    def _parse_timestamp_v1(self, ts_str: str, source: Optional[str], message: str) -> Optional[Dict[str, Any]]:
        try:
            timestamp = date_parser.parse(ts_str)
            # Default to INFO if no level indicator
            level = 'INFO'
            if any(ind in message.upper() for ind in ['ERROR', 'FATAL', 'CRITICAL']):
                level = 'ERROR'
            elif any(ind in message.upper() for ind in ['WARN', 'WARNING']):
                level = 'WARNING'
            
            return {
                'timestamp': timestamp,
                'source': source or 'Windows',
                'level': level,
                'message': message.strip(),
                'raw_line': None
            }
        except (ValueError, TypeError):
            return None
    
    def _parse_timestamp_v2(self, ts_str: str, source: Optional[str], message: str) -> Optional[Dict[str, Any]]:
        try:
            timestamp = date_parser.parse(ts_str)
            level = 'INFO'
            if any(ind in message.upper() for ind in ['ERROR', 'FATAL', 'CRITICAL']):
                level = 'ERROR'
            elif any(ind in message.upper() for ind in ['WARN', 'WARNING']):
                level = 'WARNING'
            
            return {
                'timestamp': timestamp,
                'source': source or 'Windows',
                'level': level,
                'message': message.strip(),
                'raw_line': None
            }
        except (ValueError, TypeError):
            return None


class UnknownParser(BaseParser):
    """Fallback parser for unrecognized formats - stores raw line."""
    
    def can_parse(self, line: str) -> bool:
        # Only used when no other parser matches
        return False
    
    def parse(self, line: str) -> Optional[Dict[str, Any]]:
        return {
            'timestamp': None,
            'source': 'unknown',
            'level': 'INFO',
            'message': line.strip(),
            'raw_line': line
        }
