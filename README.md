# LogSync - Multi-format Log Viewer and Correlator

A powerful tool for debugging multiple log files from different applications simultaneously. Features intelligent timestamp correlation and timeline visualization to help trace issues across distributed systems.

## Features

- **Multi-format Support**: Automatically detects and parses JSON, syslog, Apache, Python logging, Windows Event Log formats
- **Custom Parsers**: Register custom parsers via config file or runtime API for application-specific log formats
- **Timeline Correlation**: Group related events within configurable time windows (100ms - 2s)
- **Side-by-side Viewer**: View multiple log files with synchronized scrolling
- **Search & Filter**: Search by keywords, time range, log level, and source
- **Export Results**: Export filtered search results to JSON or CSV

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js (for frontend development, optional for production)

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the server
python run.py [port]
# Or use: python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# Access via browser at http://localhost:8000
```

### Usage

1. **Upload Logs**: Drag and drop multiple log files or use the file picker
2. **View Logs**: Click "View Logs" tab to see logs side-by-side with synchronized scrolling
3. **Correlate Events**: Use the "Timeline" tab to find related events across sources
4. **Search**: Filter by time range, log level, keywords, and sources

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGSYNC_PORT` | 8000 | Server port |
| `LOGSYNC_LOG_DIR` | /tmp/logsync/logs/ | Directory for stored logs |

### Custom Parsers

Edit `config/logsync_config.json` to add custom parsers:

```json
{
  "parsers": [
    {
      "name": "my_custom_format",
      "pattern": "^\\[(?P<timestamp>[^\\]]+)\\] \\[(?P<level>[\\w]+)\\] (?P<source>\\S+): (?P<message>.*)$",
      "timestamp_format": "%Y-%m-%d %H:%M:%S",
      "source_field": "source",
      "level_field": "level",
      "message_field": "message"
    }
  ]
}
```

## API Reference

### Endpoints

- `POST /api/logs` - Upload log files
- `GET /api/logs` - List uploaded logs
- `DELETE /api/logs/{id}` - Remove a file
- `GET /api/search` - Search logs with filters
- `GET /api/correlate?window_ms=500` - Find correlated events
- `POST /api/parsers` - Register custom parser

See Swagger docs at `/docs` for full API documentation.

## Architecture

```
┌─────────────────┐
│  Vue.js Frontend │
│ (Timeline, View) │
└────────┬────────┘
         │ REST API
┌────────▼────────┐
│ Python Backend  │
│ (FastAPI)       │
│ - Parser Engine │
│ - Correlator    │
│ - Search Service│
└────────┬────────┘
         │
┌────────▼────────┐
│ File System     │
│ (Temp Storage)  │
└─────────────────┘
```

## Development

### Project Structure

```
logsync/
├── src/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   ├── processors/
│   │   ├── log_parser.py    # Parser implementations
│   │   └── parser_registry.py  # Parser management
│   ├── storage/
│   │   └── file_manager.py  # File operations
│   └── api/
│       └── correlation_service.py  # Correlation logic
├── frontend/                # Vue.js application
├── config/
│   └── logsync_config.json  # Custom parser definitions
├── requirements.txt         # Python dependencies
└── run.py                   # Startup script
```

## Cross-Platform Compatibility

LogSync works on Windows, Linux, and macOS:

- Uses cross-platform temp directory storage
- Handles both Unix (`\n`) and Windows (`\r\n`) line endings
- UTF-8 encoding with latin-1 fallback for legacy logs

## License

MIT License - feel free to use and modify.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
