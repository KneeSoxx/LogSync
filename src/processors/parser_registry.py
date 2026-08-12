"""Parser registry - manages built-in and custom parsers."""
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from .log_parser import BaseParser, JSONParser, SyslogParser, ApacheParser, PythonLogParser, WindowsEventParser, UnknownParser


class ParserRegistry:
    """Manages registration and lookup of log parsers."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self._parsers: Dict[str, BaseParser] = {}
        self._config_path = config_path or Path(__file__).parent.parent / "config" / "logsync_config.json"
        
        # Initialize with built-in parsers
        self._register_builtin()
        
        # Load custom parsers from config file
        self._load_custom_parsers()
    
    def _register_builtin(self):
        """Register all built-in parsers."""
        self.register("json", JSONParser(), builtin=True)
        self.register("syslog", SyslogParser(), builtin=True)
        self.register("apache", ApacheParser(), builtin=True)
        self.register("python_log", PythonLogParser(), builtin=True)
        self.register("windows_event", WindowsEventParser(), builtin=True)
        self.register("unknown", UnknownParser(), builtin=True)
    
    def _load_custom_parsers(self):
        """Load custom parsers from config file."""
        if not self._config_path.exists():
            return
        
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for parser_config in config.get("parsers", []):
                # Create parser instance from config
                parser = self._create_parser_from_config(parser_config)
                if parser:
                    self.register(parser_config["name"], parser, builtin=False)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load custom parsers from {self._config_path}: {e}")
    
    def _create_parser_from_config(self, config: Dict[str, Any]) -> Optional[BaseParser]:
        """Create a parser instance from configuration dictionary."""
        try:
            # This is a simplified version - in production you might want more robust creation
            # For now, we'll just register the pattern for runtime registration
            name = config.get("name", "unnamed")
            
            # Store config for runtime use
            self._parsers[name] = {
                'config': config,
                'instance': None  # Will be instantiated when needed
            }
            return None  # Return None to indicate it's a placeholder
        except Exception as e:
            print(f"Error creating parser from config {name}: {e}")
            return None
    
    def register(self, name: str, parser: BaseParser, builtin: bool = False) -> bool:
        """Register a new parser by name."""
        if name in self._parsers:
            # If it's a placeholder, replace with actual instance
            if isinstance(self._parsers[name], dict):
                del self._parsers[name]
        
        self._parsers[name] = parser
        return True
    
    def get_parser(self, name: str) -> Optional[BaseParser]:
        """Get parser by name."""
        if isinstance(self._parsers.get(name), BaseParser):
            return self._parsers[name]
        elif isinstance(self._parsers.get(name), dict):
            # Try to instantiate from config
            config = self._parsers[name]['config']
            pattern = config.get('pattern', '')
            
            # Create a dynamic parser class
            class CustomParser(BaseParser):
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
                    
                    # Extract timestamp
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
            
            parser = CustomParser(
                pattern=pattern,
                timestamp_format=config.get('timestamp_format', '%Y-%m-%d %H:%M:%S'),
                field_mappings=config.get('field_mappings', {}),
                source_field=config.get('source_field', 'source'),
                level_field=config.get('level_field', 'level'),
                message_field=config.get('message_field', 'message')
            )
            
            self._parsers[name] = parser
        
        return self._parsers.get(name)
    
    def get_all_parsers(self) -> Dict[str, BaseParser]:
        """Get all registered parsers."""
        return {name: parser for name, parser in self._parsers.items() 
                if isinstance(parser, BaseParser)}
    
    def get_builtin_names(self) -> List[str]:
        """Get list of built-in parser names."""
        return [name for name, parser in self._parsers.items() 
                if isinstance(parser, BaseParser) and getattr(parser, '__module__', '') != '']
    
    def detect_format(self, line: str) -> Optional[str]:
        """Auto-detect the format of a log line using priority order."""
        config = json.loads(Path(__file__).parent.parent / "config" / "logsync_config.json").read_text() if (Path(__file__).parent.parent / "config" / "logsync_config.json").exists() else {}
        
        order = config.get("auto_detect_order", ["json", "syslog", "apache", "python_log", "windows_event"])
        
        for name in order:
            parser = self.get_parser(name)
            if parser and parser.can_parse(line):
                return name
        
        return None
    
    def detect_with_fallback(self, line: str, custom_parsers: List[str] = None) -> Optional[str]:
        """Detect format with smart fallback: built-in first, then custom."""
        # Try built-in parsers first
        for parser in self.get_all_parsers().values():
            if parser.can_parse(line):
                return parser.__class__.__name__.replace('Parser', '').lower()
        
        # Try custom parsers
        if custom_parsers:
            for name in custom_parsers:
                parser = self.get_parser(name)
                if parser and parser.can_parse(line):
                    return name
        
        return None
    
    def parse_line(self, line: str, parser_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse a log line using specified or auto-detected parser."""
        if not parser_name:
            parser_name = self.detect_format(line)
        
        if not parser_name:
            # Try with fallback
            custom_names = [name for name, p in self._parsers.items() 
                          if isinstance(p, dict)]
            parser_name = self.detect_with_fallback(line, custom_names)
        
        if not parser_name:
            return None
        
        parser = self.get_parser(parser_name)
        if parser:
            return parser.parse(line)
        
        return None


# Global registry instance
_registry_instance = None

def get_registry(config_path: Optional[Path] = None) -> ParserRegistry:
    """Get or create the global parser registry."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ParserRegistry(config_path)
    return _registry_instance


def reset_registry():
    """Reset the global registry (useful for testing)."""
    global _registry_instance
    _registry_instance = None
