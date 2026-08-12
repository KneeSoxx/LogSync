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
- Node.js 18+ (for building frontend)
- npm or yarn

### Development Setup (Recommended)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install

# Start backend server
python run.py 8000

# Open browser at http://localhost:8000

# To develop frontend with hot reload, start in another terminal:
cd frontend
npm run dev
```

### Production Setup (Static Files)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Build optimized frontend
cd frontend
npm run build

# Run the server (it will serve built static files from frontend/dist/)
python run.py 8000

# Access via browser at http://localhost:8000
```

### Minimal Setup (No Node.js)

If you don't have Node.js, you can still use the API directly:

```bash
pip install -r requirements.txt
python run.py 8000
# Access Swagger UI at http://localhost:8000/docs
```

### Usage

1. **Upload Logs**: Drag and drop multiple log files or use the file picker
2. **View Logs**: Click "View Logs" tab to see logs side-by-side with synchronized scrolling
3. **Correlate Events**: Use the "Correlate" tab to find related events across sources
4. **Search**: Filter by time range, log level, keywords, and sources

### Frontend Development

```bash
cd frontend
npm run dev
# Opens at http://localhost:5173
```

### Building for Production

```bash
cd frontend
npm run build
# Output in frontend/dist/
```

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

- `POST /api/logs` - Upload log files (supports stream mode)
- `GET /api/logs` - List uploaded logs
- `DELETE /api/logs/{id}` - Remove a file
- `GET /api/streams` - List all log streams
- `DELETE /api/streams/{stream_id}` - Delete a stream and its files
- `GET /api/search` - Search logs with filters
- `POST /api/correlate` - Find correlated events (supports stream correlation)
- `POST /api/parsers` - Register custom parser

See Swagger docs at `/docs` for full API documentation.

## Project Structure

```
logsync/
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── run.py                         # Startup script
├── .gitignore                     # Git ignore rules
│
├── config/
│   └── logsync_config.json        # Custom parser definitions
│
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── models.py                  # Pydantic data models
│   ├── storage/
│   │   └── file_manager.py        # Cross-platform file operations
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── log_parser.py          # 5 built-in parsers + custom support
│   │   └── parser_registry.py     # Parser registration (config + runtime)
│   └── api/
│       ├── correlation_service.py # Correlation logic (500ms windows)
│       └── search_service.py      # Search with inverted index
│
├── frontend/                      # Vue.js 3 application
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js             # Vite bundler config
│   ├── tailwind.config.js         # Tailwind CSS config
│   └── src/
│       ├── main.js                # Vue app entry
│       ├── App.vue                # Root component with upload/viewer/tabs
│       ├── components/
│       │   ├── CorrelationView.vue  # Correlation timeline UI
│       │   ├── Timeline.vue         # Time-based visualization
│       │   └── SearchPanel.vue      # Enhanced search with filters
│       ├── style.css              # Global styles (Tailwind)
│       └── public/                # Static assets
│
└── logs/                          # Empty directory for reference
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
