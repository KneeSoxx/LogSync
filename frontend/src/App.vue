<template>
  <div class="app-container">
    <header class="header">
      <h1 class="logo">📋 LogSync</h1>
      <nav class="nav-tabs">
        <button @click="view = 'upload'" :class="{ active: view === 'upload' }">Upload Logs</button>
        <button @click="view = 'viewer'" :class="{ active: view === 'viewer' && selectedFiles.length > 0 }">View Logs ({{ selectedFiles.length }})</button>
      </nav>
    </header>

    <main class="main-content">
      <!-- Upload View -->
      <div v-if="view === 'upload'" class="upload-section">
        <h2>Upload Log Files</h2>
        <div class="drop-zone" @dragover.prevent @drop="handleDrop">
          <p class="drop-text">Drag and drop log files here, or click to select</p>
          <input type="file" multiple accept=".log,.txt" @change="handleFileSelect" class="file-input" />
        </div>
        
        <div v-if="uploadQueue.length > 0" class="queue-section">
          <h3>Processing Queue ({{ uploadQueue.length }})</h3>
          <ul class="queue-list">
            <li v-for="(file, index) in uploadQueue" :key="index">
              <span class="filename">{{ file.name }}</span>
              <span v-if="file.status === 'complete'" class="status-success">✓</span>
              <span v-else-if="file.status === 'error'" class="status-error">✗ {{ file.error }}</span>
              <span v-else class="status-pending">⏳</span>
            </li>
          </ul>
        </div>

        <button @click="uploadFiles" :disabled="uploadQueue.length === 0 || uploading" class="btn-primary">
          {{ uploading ? 'Uploading...' : 'Upload Files' }}
        </button>
      </div>

      <!-- Viewer View -->
      <div v-if="view === 'viewer' && selectedFiles.length > 0" class="viewer-section">
        <div class="viewer-header">
          <h2>Log Viewer ({{ selectedFiles.length }} files)</h2>
          <div class="file-selector">
            <select v-model="selectedFileIndex" @change="onFileSelectChange">
              <option :value="-1">All Files</option>
              <option v-for="(file, index) in selectedFiles" :key="file.id" :value="index">
                {{ file.filename }} ({{ formatBytes(file.size_bytes) }})
              </option>
            </select>
          </div>
        </div>

        <!-- File Tabs -->
        <div class="tabs-container">
          <button 
            v-for="(file, index) in selectedFiles" 
            :key="file.id"
            @click="activeTab = index"
            :class="{ active: activeTab === index }"
            class="tab-button"
          >
            {{ file.filename }}
            <span class="line-count">{{ formatNumber(file.line_count) }} lines</span>
          </button>
        </div>

        <!-- Log Content Panels -->
        <div class="panels-container">
          <div 
            v-for="(file, index) in selectedFiles" 
            :key="file.id"
            class="panel"
            ref="panels"
            @scroll="syncScroll(index)"
          >
            <div class="panel-header">
              <span class="panel-title">{{ file.filename }}</span>
              <span v-if="file.detected_format" class="format-badge">{{ file.detected_format }}</span>
            </div>
            <div 
              class="log-content"
              ref="logContents"
              @scroll="handlePanelScroll(index)"
            >
              <template v-for="(line, lineIndex) in parsedLines[index]" :key="lineIndex">
                <div class="log-line" :class="getLogLevelClass(line.level)">
                  <span class="timestamp">{{ formatTimestamp(line.timestamp) }}</span>
                  <span class="level">{{ line.level }}</span>
                  <span class="message">{{ line.message }}</span>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Search Panel -->
        <div class="search-panel">
          <h3>Search & Filter</h3>
          <div class="search-controls">
            <input v-model="searchQuery" type="text" placeholder="Search logs..." @keyup.enter="performSearch" />
            <button @click="performSearch" class="btn-secondary">Search</button>
          </div>
          <div class="filter-controls">
            <label>Log Level:</label>
            <select v-model="selectedLogLevel" @change="applyFilters">
              <option value="">All Levels</option>
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="empty-state">
        <h2>Welcome to LogSync</h2>
        <p>Select the "Upload Logs" tab to begin.</p>
      </div>
    </main>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'App',
  data() {
    return {
      view: 'upload',
      uploadQueue: [],
      uploading: false,
      selectedFiles: [],
      selectedFileIndex: -1,
      activeTab: 0,
      searchQuery: '',
      selectedLogLevel: '',
      parsedLines: {},
      allSearchResults: []
    }
  },
  mounted() {
    // Check for saved state
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

    handleFileSelect(event) {
      const files = Array.from(event.target.files).filter(f => 
        f.name.endsWith('.log') || f.name.endsWith('.txt')
      )
      this.addFiles(files)
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

        const response = await axios.post('/api/logs', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })

        // Store uploaded files
        this.selectedFiles.push(...response.data.files)
        
        // Mark as complete
        this.uploadQueue.forEach(item => {
          item.status = 'complete'
        })

        // Save state
        this.saveState()

      } catch (error) {
        this.uploadQueue.forEach(item => {
          item.status = 'error'
          item.error = error.response?.data?.detail || 'Upload failed'
        })
      } finally {
        this.uploading = false
        
        // Clear queue after delay
        setTimeout(() => {
          this.uploadQueue = []
        }, 3000)
      }
    },

    onFileSelectChange() {
      if (this.selectedFileIndex >= 0 && this.selectedFiles[this.selectedFileIndex]) {
        this.activeTab = this.selectedFileIndex
        this.loadFileLines(this.selectedFileIndex)
      } else {
        this.activeTab = 0
        if (this.selectedFiles[0]) {
          this.loadFileLines(0)
        }
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

    async performSearch() {
      try {
        const params = {}
        if (this.searchQuery) params.query = this.searchQuery
        if (this.selectedLogLevel) params.level = this.selectedLogLevel
        
        const response = await axios.get('/api/search', { params })
        this.allSearchResults = response.data.results || []
      } catch (error) {
        console.error('Search failed:', error)
      }
    },

    applyFilters() {
      // Re-apply current search with new level filter
      if (this.searchQuery || this.selectedLogLevel) {
        this.performSearch()
      }
    },

    handlePanelScroll(fileIndex) {
      const panels = this.$refs.panels
      if (panels && panels.length > 0) {
        panels[fileIndex].scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    },

    syncScroll(activeFileIndex) {
      const panels = this.$refs.panels
      if (panels && activeFileIndex >= 0 && activeFileIndex < panels.length - 1) {
        // Scroll other panels to match active one
        for (let i = 0; i < panels.length; i++) {
          if (i !== activeFileIndex) {
            panels[i].scrollTo(panels[activeFileIndex].scrollTop, panels[activeFileIndex].scrollLeft)
          }
        }
      }
    },

    getLogLevelClass(level) {
      const upper = level?.toUpperCase() || ''
      if (upper === 'ERROR') return 'level-error'
      if (upper === 'WARNING') return 'level-warning'
      if (upper === 'INFO') return 'level-info'
      if (upper === 'DEBUG') return 'level-debug'
      return ''
    },

    formatTimestamp(ts) {
      if (!ts) return '-'
      try {
        const date = new Date(ts)
        return date.toLocaleTimeString()
      } catch (e) {
        return ts
      }
    },

    formatBytes(bytes) {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    },

    formatNumber(num) {
      if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
      if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
      return num.toString()
    },

    saveState() {
      const state = {
        view: this.view,
        selectedFiles: this.selectedFiles
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

.upload-section, .viewer-section, .empty-state {
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
  transition: transform 0.2s, box-shadow 0.2s;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.queue-section {
  background: #1e1e30;
  padding: 1rem;
  border-radius: 8px;
}

.queue-list {
  list-style: none;
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.queue-list li {
  background: #2a2a40;
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

.status-success { color: #4ade80; }
.status-error { color: #f87171; }
.status-pending { color: #60a5fa; }

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
  transition: all 0.2s;
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
  height: calc(100vh - 300px);
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
  border-bottom: 1px solid #333;
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

.empty-state h2 {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

@media (max-width: 768px) {
  .panels-container {
    flex-direction: column;
  }
  
  .log-line {
    grid-template-columns: 1fr;
    gap: 0.25rem;
  }
  
  .log-line .timestamp,
  .log-line .level {
    display: none;
  }
}
</style>
