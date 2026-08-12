<template>
  <div class="app-container">
    <header class="header">
      <h1 class="logo">📋 LogSync</h1>
      <nav class="nav-tabs">
        <button @click="view = 'upload'" :class="{ active: view === 'upload' }">Upload Logs</button>
        <button @click="view = 'streams'" :class="{ active: view === 'streams' }">Streams ({{ streamsList.length }})</button>
        <button @click="view = 'correlate'" :class="{ active: view === 'correlate' }">Correlate</button>
      </nav>
    </header>

    <main class="main-content">
      <!-- Upload View -->
      <div v-if="view === 'upload'" class="upload-section">
        <h2>Upload Log Files (Single or Stream Mode)</h2>
        <div class="upload-options">
          <label class="radio-group">
            <input type="radio" v-model="uploadMode" value="single" checked />
            <span>Individual Upload</span>
          </label>
          <label class="radio-group">
            <input type="radio" v-model="uploadMode" value="stream" />
            <span>Stream Mode (link files as unified stream)</span>
          </label>
        </div>
        
        <div v-if="uploadMode === 'stream'" class="stream-name-input">
          <input v-model="streamName" type="text" placeholder="Enter stream name (e.g., production-app)" />
        </div>
        
        <div class="drop-zone" @dragover.prevent @drop="handleDrop">
          <p class="drop-text">Drag and drop log files here, or click to select</p>
          <input type="file" multiple accept=".log,.txt" @change="handleFileSelect" class="file-input" />
        </div>
        
        <div v-if="uploadQueue.length > 0" class="queue-section">
          <h3>Processing Queue ({{ uploadQueue.length }})</h3>
          <ul class="queue-list">
            <li v-for="(item, index) in uploadQueue" :key="index">
              <span class="filename">{{ item.name }}</span>
              <span v-if="item.status === 'complete'" class="status-success">✓</span>
              <span v-else-if="item.status === 'error'" class="status-error">✗ {{ item.error }}</span>
              <span v-else class="status-pending">⏳</span>
            </li>
          </ul>
        </div>

        <button @click="uploadFiles" :disabled="uploading || uploadQueue.length === 0" class="btn-primary">
          {{ uploading ? 'Uploading...' : 'Upload Files' }}
        </button>
      </div>

      <!-- Streams View -->
      <div v-if="view === 'streams'" class="streams-section">
        <h2>Log Streams</h2>
        <p class="stream-desc">Groups of files that are treated as a single unified log stream for correlation.</p>
        
        <div v-if="streamsList.length === 0" class="empty-state">
          <p>No streams yet. Upload multiple files together to create a stream.</p>
        </div>
        
        <div v-else class="stream-grid">
          <div v-for="stream in streamsList" :key="stream.id" class="stream-card">
            <h3>{{ stream.name }}</h3>
            <div class="stream-meta">
              <span class="badge">{{ stream.file_count }} file(s)</span>
              <span class="badge">{{ formatBytes(stream.total_size) }}</span>
              <span class="badge">{{ stream.total_lines.toLocaleString() }} lines</span>
            </div>
            <ul class="stream-files">
              <li v-for="file in stream.files" :key="file.id" :class="{ 'linked': true }">
                {{ file.filename }} ({{ file.line_count }} lines)
              </li>
            </ul>
            <div class="stream-actions">
              <button @click="viewCorrelateStream(stream.id)" class="btn-small">Correlate</button>
              <button @click="deleteStream(stream.id)" class="btn-small btn-danger">Delete</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Correlate View -->
      <div v-if="view === 'correlate'" class="correlate-section">
        <h2>Correlation Engine</h2>
        <p class="correlate-desc">Find related events across your logs using time-based correlation.</p>
        
        <div class="correlate-controls">
          <label>Time Window (ms):</label>
          <input type="range" v-model="correlationWindow" min="100" max="2000" :step="100" />
          <span>{{ correlationWindow }}ms</span>
        </div>
        
        <div class="correlate-options">
          <label>
            <input type="radio" v-model="correlationTarget" value="all" checked />
            All Files
          </label>
          <label>
            <input type="radio" v-model="correlationTarget" value="stream" />
            Selected Stream
          </label>
        </div>

        <div class="drop-zone correlate-drop" @dragover.prevent @drop="handleStreamDrop">
          <p class="drop-text">Or drag files here to create a new stream for correlation</p>
          <input type="file" multiple accept=".log,.txt" @change="handleStreamFileSelect" class="file-input" />
        </div>

        <button @click="performCorrelation" :disabled="correlating || !hasCorrelatableData" class="btn-primary">
          {{ correlating ? 'Correlating...' : 'Run Correlation' }}
        </button>

        <div v-if="correlationResults && correlationResults.groups.length > 0" class="correlation-results">
          <h3>{{ correlationResults.total_groups }} Correlation Groups Found</h3>
          
          <ul class="groups-list">
            <li v-for="(group, index) in correlationResults.groups" :key="index" class="group-item" @click="viewGroupDetails(index)">
              <div class="group-header">
                <span class="group-id">{{ group.group_id }}</span>
                <span class="event-count">{{ group.event_count }} events</span>
                <span class="time-span">{{ group.time_span_ms }}ms</span>
              </div>
              <div v-if="group.stream_id" class="stream-badge">Stream: {{ group.stream_name }}</div>
              <div class="group-events">
                <div v-for="(event, eIndex) in group.events.slice(0, 3)" :key="eIndex" class="event-row">
                  <span class="event-time">{{ formatTime(event.timestamp) }}</span>
                  <span class="event-level">{{ event.level }}</span>
                  <span class="event-source">{{ event.source }}</span>
                  <span class="event-msg">{{ truncate(event.message, 80) }}</span>
                </div>
                <div v-if="group.events.length > 3" class="more-events">+{{ group.events.length - 3 }} more events</div>
              </div>
            </li>
          </ul>
        </div>

        <div v-else-if="correlationResults" class="empty-correlation">
          <p>No correlation groups found or click "Run Correlation" to analyze.</p>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="empty-state">
        <h2>Welcome to LogSync</h2>
        <p>Select a tab to get started.</p>
      </div>
    </main>
  </div>
</template>

<script>
import CorrelationView from './components/CorrelationView.vue'
import axios from 'axios'

export default {
  name: 'App',
  components: {
    CorrelationView
  },
  data() {
    return {
      view: 'upload',
      uploadQueue: [],
      uploading: false,
      selectedFiles: [],
      streamName: '',
      uploadMode: 'single', // 'single' or 'stream'
      streamsList: [],
      correlationWindow: 500,
      correlationTarget: 'all', // 'all' or 'stream'
      correlationResults: null,
      correlating: false,
      hasCorrelatableData: true,
      allSearchResults: []
    }
  },
  mounted() {
    const savedState = localStorage.getItem('logsync_state')
    if (savedState) {
      try {
        const state = JSON.parse(savedState)
        this.view = state.view || 'upload'
        this.selectedFiles = state.selectedFiles || []
      } catch(e) {}
    }
  },
  methods: {
    async handleDrop(event) {
      const files = Array.from(event.dataTransfer.files).filter(f => 
        f.name.endsWith('.log') || f.name.endsWith('.txt')
      )
      this.addFiles(files)
    },

    handleStreamDrop(event) {
      const files = Array.from(event.dataTransfer.files).filter(f => 
        f.name.endsWith('.log') || f.name.endsWith('.txt')
      )
      if (files.length > 0 && this.correlationTarget === 'stream') {
        // Create a new stream from dragged files
        this.streamName = `Stream ${this.streamsList.length + 1}`
        this.uploadMode = 'stream'
        this.addFiles(files)
      }
    },

    handleFileSelect(event) {
      const files = Array.from(event.target.files).filter(f => 
        f.name.endsWith('.log') || f.name.endsWith('.txt')
      )
      this.addFiles(files)
    },

    handleStreamFileSelect(event) {
      const files = Array.from(event.target.files).filter(f => 
        f.name.endsWith('.log') || f.name.endsWith('.txt')
      )
      if (files.length > 0 && this.correlationTarget === 'stream') {
        this.streamName = `Stream ${this.streamsList.length + 1}`
        this.uploadMode = 'stream'
        this.addFiles(files)
      }
    },

    addFiles(files) {
      this.uploadQueue.push(...files.map(f => ({
        file: f,
        name: f.name,
        status: 'pending'
      })))
    },

    async uploadFiles() {
      if (this.uploading || this.uploadQueue.length === 0) return
      
      this.uploading = true
      
      try {
        const formData = new FormData()
        for (const item of this.uploadQueue) {
          formData.append('files', item.file)
        }
        
        // Add stream_id if in stream mode
        if (this.uploadMode === 'stream' && this.streamName.trim()) {
          formData.append('stream_id', this.streamName.trim())
        }

        const response = await axios.post('/api/logs', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })

        // Add uploaded files to selectedFiles
        if (response.data.files) {
          this.selectedFiles.push(...response.data.files)
          
          // If in stream mode, group them into a stream
          if (this.uploadMode === 'stream' && response.data.stream_id) {
            const stream = {
              id: response.data.stream_id,
              name: this.streamName || `Stream ${this.streamsList.length + 1}`,
              file_count: response.data.files.length,
              total_size: response.data.files.reduce((sum, f) => sum + (f.size_bytes || 0), 0),
              total_lines: response.data.files.reduce((sum, f) => sum + (f.line_count || 0), 0),
              files: response.data.files.map(f => ({
                id: f.id,
                filename: f.filename,
                size_bytes: f.size_bytes,
                line_count: f.line_count
              }))
            }
            
            // Check if stream already exists
            const existingIndex = this.streamsList.findIndex(s => s.id === response.data.stream_id)
            if (existingIndex >= 0) {
              // Update existing stream
              this.streamsList[existingIndex] = stream
            } else {
              this.streamsList.push(stream)
            }
          }
        }

        this.uploadQueue.forEach(item => { item.status = 'complete' })
        this.saveState()

      } catch (error) {
        this.uploadQueue.forEach(item => {
          item.status = 'error'
          item.error = error.response?.data?.detail || 'Upload failed'
        })
      } finally {
        this.uploading = false
        
        setTimeout(() => {
          this.uploadQueue = []
        }, 3000)
      }
    },

    async loadFileLines(fileIndex) {
      const file = this.selectedFiles[fileIndex]
      if (!file) return

      try {
        const response = await axios.get(`/api/files/${file.id}/lines`, { params: { limit: 1000 } })
        this.parsedLines[fileIndex] = response.data.lines || []
      } catch (error) {
        console.error('Failed to load lines:', error)
      }
    },

    async loadStreams() {
      try {
        const response = await axios.get('/api/streams')
        this.streamsList = response.data.streams || []
      } catch (error) {
        console.error('Failed to load streams:', error)
      }
    },

    async performCorrelation() {
      if (!this.hasCorrelatableData) return
      
      this.correlating = true
      this.correlationResults = null
      
      try {
        const params = {
          window_ms: this.correlationWindow
        }
        
        if (this.correlationTarget === 'stream' && this.streamsList.length > 0) {
          // Use the first stream for correlation
          params.stream_id = this.streamsList[0].id
        }
        
        const response = await axios.post('/api/correlate', null, { params })
        this.correlationResults = response.data
        
      } catch (error) {
        console.error('Correlation failed:', error)
      } finally {
        this.correlating = false
      }
    },

    deleteStream(streamId) {
      if (!confirm(`Are you sure you want to delete stream "${streamId}" and all its files?`)) return
      
      axios.delete(`/api/streams/${streamId}`)
        .then(() => {
          this.streamsList = this.streamsList.filter(s => s.id !== streamId)
          // Clear correlation results if we deleted the targeted stream
          if (this.correlationTarget === 'stream' && this.correlationResults?.stream_id === streamId) {
            this.correlationResults = null
          }
        })
        .catch(error => {
          console.error('Failed to delete stream:', error)
          alert('Failed to delete stream')
        })
    },

    viewCorrelateStream(streamId) {
      this.correlationTarget = 'stream'
      this.view = 'correlate'
      
      // Select the first file in the stream to upload (creates a temporary selection)
      const stream = this.streamsList.find(s => s.id === streamId)
      if (stream && stream.files.length > 0) {
        this.selectedFiles = [{ id: 'temp', filename: `${stream.name} correlation` }]
      }
    },

    truncate(str, len) {
      return str.length > len ? str.substring(0, len) + '...' : str
    },

    formatTime(timeStr) {
      if (!timeStr) return '-'
      try {
        const date = new Date(timeStr)
        return date.toLocaleTimeString()
      } catch (e) {
        return timeStr
      }
    },

    formatBytes(bytes) {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    },

    saveState() {
      const state = {
        view: this.view,
        selectedFiles: this.selectedFiles,
        streamsList: this.streamsList
      }
      localStorage.setItem('logsync_state', JSON.stringify(state))
    }
  }
}
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
}

.nav-tabs {
  display: flex;
  gap: 0.5rem;
}

.nav-tabs button {
  background: rgba(255,255,255,0.2);
  border: none;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-tabs button:hover {
  background: rgba(255,255,255,0.3);
}

.nav-tabs button.active {
  background: white;
  color: #667eea;
  font-weight: bold;
}

.main-content {
  flex: 1;
  padding: 1rem 2rem;
  overflow: hidden;
}

.upload-section, .viewer-section, .timeline-section, .empty-state {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.drop-zone {
  border: 3px dashed #667eea;
  border-radius: 8px;
  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.drop-zone:hover {
  background: rgba(102, 126, 234, 0.1);
  border-color: #764ba2;
}

.drop-text {
  color: #888;
  margin-bottom: 1rem;
}

.file-input {
  display: none;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 0.75rem 2rem;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.file-selector select {
  background: #1e1e30;
  color: white;
  border: 1px solid #444;
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

.tabs-container {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1rem;
  overflow-x: auto;
  padding-bottom: 0.5rem;
}

.tab-button {
  background: #1e1e30;
  color: #aaa;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  white-space: nowrap;
}

.tab-button:hover {
  background: #2a2a40;
}

.tab-button.active {
  background: #667eea;
  color: white;
}

.panels-container {
  display: flex;
  gap: 1rem;
  height: calc(100vh - 350px);
  min-height: 400px;
}

.panel {
  flex: 1;
  background: #1e1e30;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 0.75rem;
  background: #2a2a40;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-title {
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.format-badge {
  background: #667eea;
  color: white;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
  background: #1a1a2e;
}

.log-line {
  display: grid;
  grid-template-columns: 120px 80px 1fr;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid #2a2a40;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.log-line .timestamp { color: #888; }
.log-line .level { font-weight: bold; }
.log-line .message { word-break: break-word; }

.level-error .level { color: #f87171; }
.level-warning .level { color: #fbbf24; }
.level-info .level { color: #60a5fa; }
.level-debug .level { color: #34d399; }

.search-panel {
  background: #1e1e30;
  padding: 1rem;
  border-radius: 8px;
}

.search-controls, .filter-controls {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.search-controls input {
  flex: 1;
  background: #2a2a40;
  border: 1px solid #444;
  color: white;
  padding: 0.5rem;
  border-radius: 4px;
}

.btn-secondary {
  background: #444;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.empty-state {
  justify-content: center;
  align-items: center;
  height: 100%;
  text-align: center;
  color: #888;
}

.upload-options {
  display: flex;
  gap: 2rem;
  margin-bottom: 1rem;
}

.radio-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.radio-group input[type="radio"] {
  accent-color: #667eea;
}

.stream-name-input {
  margin-bottom: 1rem;
}

.stream-name-input input {
  background: #1e1e30;
  border: 1px solid #444;
  color: white;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  width: 300px;
}

.streams-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stream-desc {
  color: #888;
}

.stream-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.stream-card {
  background: #1e1e30;
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid #333;
}

.stream-card h3 {
  margin-top: 0;
  color: #667eea;
}

.stream-meta {
  display: flex;
  gap: 0.5rem;
  margin: 0.75rem 0;
  flex-wrap: wrap;
}

.badge {
  background: #333;
  color: #aaa;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.stream-files {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem 0;
  max-height: 200px;
  overflow-y: auto;
}

.stream-files li {
  padding: 0.25rem 0;
  color: #aaa;
  font-size: 0.875rem;
  border-bottom: 1px solid #2a2a40;
}

.stream-card.linked .stream-files li {
  color: #60a5fa;
}

.stream-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-small {
  flex: 1;
  padding: 0.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
}

.btn-small.btn-danger {
  background: #dc2626;
  color: white;
}

.btn-small:hover {
  opacity: 0.9;
}

.correlate-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.correlate-desc {
  color: #888;
}

.correlate-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: #1e1e30;
  border-radius: 8px;
}

.correlate-options {
  display: flex;
  gap: 1.5rem;
  padding: 1rem;
  background: #1e1e30;
  border-radius: 8px;
}

.correlate-drop {
  margin-bottom: 1rem;
}

.group-item {
  background: #1e1e30;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.group-item:hover {
  border-color: #667eea;
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.group-id {
  font-weight: bold;
  color: #667eea;
}

.event-count, .time-span {
  color: #888;
  font-size: 0.875rem;
}

.stream-badge {
  display: block;
  margin-top: 0.5rem;
  color: #60a5fa;
  font-size: 0.875rem;
}

.group-events {
  margin-top: 0.5rem;
}

.event-row {
  display: grid;
  grid-template-columns: 120px 80px 100px 1fr;
  gap: 0.5rem;
  padding: 0.5rem;
  background: #2a2a40;
  border-radius: 4px;
  font-size: 0.875rem;
}

.event-time, .event-level, .event-source {
  font-weight: bold;
}

.more-events {
  color: #60a5fa;
  font-size: 0.875rem;
  margin-top: 0.5rem;
}

.empty-correlation {
  text-align: center;
  padding: 3rem;
  color: #888;
}

.empty-state h2 {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}
</style>
