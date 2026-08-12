<template>
  <div class="search-panel">
    <h3>Search & Filter</h3>
    
    <!-- Search Input -->
    <div class="search-input-group">
      <input 
        v-model="searchQuery" 
        type="text" 
        placeholder="Search logs (press Enter)..." 
        @keyup.enter="performSearch"
        class="search-input"
      />
      <button @click="performSearch" class="search-btn">
        🔍 Search
      </button>
    </div>

    <!-- Filters -->
    <div class="filters-section">
      <div class="filter-row">
        <label class="filter-label">Log Level:</label>
        <select v-model="selectedLevel" @change="applyFilters" class="filter-select">
          <option value="">All Levels</option>
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>
      </div>

      <div class="filter-row">
        <label class="filter-label">Time Range:</label>
        <div class="time-range-inputs">
          <input type="datetime-local" v-model="startTime" @change="applyFilters" class="time-input">
          <span class="range-separator">to</span>
          <input type="datetime-local" v-model="endTime" @change="applyFilters" class="time-input">
        </div>
      </div>

      <div class="filter-row">
        <label class="filter-label">Sources:</label>
        <select v-model="selectedSource" @change="applyFilters" class="filter-select">
          <option value="">All Sources</option>
          <option v-for="source in uniqueSources" :key="source" :value="source">{{ source }}</option>
        </select>
      </div>
    </div>

    <!-- Results Info -->
    <div v-if="searchResults.length > 0" class="results-info">
      <span>Found {{ searchResults.length }} results</span>
      <button @click="exportResults" :disabled="exporting" class="export-btn">
        {{ exporting ? 'Exporting...' : '📥 Export Results' }}
      </button>
    </div>

    <!-- Search Results -->
    <div v-if="searchResults.length > 0" class="results-list">
      <div 
        v-for="(result, idx) in searchResults" 
        :key="idx"
        class="result-item"
        @click="viewResult(result)"
      >
        <div class="result-meta">
          <span class="result-time">{{ formatTime(result.timestamp) }}</span>
          <span class="result-level" :class="'lvl-' + result.level.toLowerCase()">{{ result.level }}</span>
        </div>
        <div class="result-content">
          <span class="result-source">{{ result.source }}</span>
          <span class="result-message">{{ result.message }}</span>
        </div>
        <div class="result-file">
          {{ result.file }}:{{ result.line_number }}
        </div>
      </div>
    </div>

    <div v-else-if="searchQuery && searchResults.length === 0" class="no-results">
      <p>No results found for "{{ searchQuery }}"</p>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'SearchPanel',
  data() {
    return {
      searchQuery: '',
      selectedLevel: '',
      selectedSource: '',
      startTime: '',
      endTime: '',
      uniqueSources: [],
      searchResults: [],
      exporting: false
    }
  },
  methods: {
    async performSearch() {
      if (!this.searchQuery && !this.selectedLevel && !this.startTime && !this.endTime) {
        this.searchResults = []
        return
      }

      try {
        const params = {}
        if (this.searchQuery) params.query = this.searchQuery
        if (this.startTime) {
          const d = new Date(this.startTime)
          params.start = d.toISOString().slice(0, 16)
        }
        if (this.endTime) {
          const d = new Date(this.endTime)
          params.end = d.toISOString().slice(0, 16)
        }
        if (this.selectedLevel) params.level = this.selectedLevel
        if (this.selectedSource) params.sources = this.selectedSource
        
        const response = await axios.get('/api/search', { params })
        this.searchResults = response.data.results || []
        this.uniqueSources = [...new Set(this.searchResults.map(r => r.source))]
      } catch (error) {
        console.error('Search failed:', error)
        alert('Search failed. Please check the logs.')
      }
    },

    applyFilters() {
      this.performSearch()
    },

    async exportResults() {
      this.exporting = true
      
      try {
        const params = {}
        if (this.startTime) params.start = this.startTime
        if (this.endTime) params.end = this.endTime
        if (this.selectedLevel) params.level = this.selectedLevel
        
        const response = await axios.post('/api/search/export', {}, { params })
        
        // Trigger download
        const link = document.createElement('a')
        link.href = response.data.file_path
        link.download = `logsync_export_${response.data.export_id}.json`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        
        alert(`Exported ${response.data.result_count} results!`)
      } catch (error) {
        console.error('Export failed:', error)
        alert('Export failed. Please try again.')
      } finally {
        this.exporting = false
      }
    },

    viewResult(result) {
      // Open side-by-side viewer for this file and line
      alert(`View logs from ${result.file} starting at line ${result.line_number}`)
    },

    formatTime(timestamp) {
      try {
        const date = new Date(timestamp)
        return date.toLocaleTimeString('en-US', { 
          hour: '2-digit', 
          minute: '2-digit', 
          second: '2-digit'
        })
      } catch (e) {
        return timestamp
      }
    }
  }
}
</script>

<style scoped>
.search-panel {
  background: #1e1e30;
  padding: 1.5rem;
  border-radius: 8px;
  margin-top: 1rem;
}

.search-panel h3 {
  font-size: 1rem;
  color: #fff;
  margin-bottom: 1rem;
}

.search-input-group {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.search-input {
  flex: 1;
  background: #2a2a40;
  border: 1px solid #444;
  color: white;
  padding: 0.625rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.search-input:focus {
  outline: none;
  border-color: #667eea;
}

.search-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 0.625rem 1.25rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  transition: transform 0.2s;
}

.search-btn:hover {
  transform: translateY(-1px);
}

.filters-section {
  background: #2a2a40;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.filter-row:last-child {
  margin-bottom: 0;
}

.filter-label {
  min-width: 80px;
  color: #aaa;
  font-size: 0.875rem;
}

.filter-select {
  background: #1a1a2e;
  color: white;
  border: 1px solid #444;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.time-range-inputs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.time-input {
  background: #1a1a2e;
  color: white;
  border: 1px solid #444;
  padding: 0.5rem;
  border-radius: 4px;
  font-size: 0.875rem;
}

.range-separator {
  color: #667eea;
  font-weight: bold;
}

.results-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.results-info span {
  color: #fff;
  font-weight: bold;
}

.export-btn {
  background: #4ade80;
  color: #1a1a2e;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.2s;
}

.export-btn:hover:not(:disabled) {
  background: #22c55e;
  transform: translateY(-1px);
}

.export-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.results-list {
  max-height: 400px;
  overflow-y: auto;
  background: #1a1a2e;
  border-radius: 6px;
}

.result-item {
  padding: 1rem;
  border-bottom: 1px solid #2a2a40;
  cursor: pointer;
  transition: background 0.2s;
}

.result-item:last-child {
  border-bottom: none;
}

.result-item:hover {
  background: rgba(102, 126, 234, 0.1);
}

.result-meta {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.result-time {
  color: #888;
  font-size: 0.75rem;
  font-family: monospace;
}

.result-level {
  padding: 0.2rem 0.5rem;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: bold;
}

.lvl-error { background: rgba(248, 113, 113, 0.2); color: #f87171; }
.lvl-warning { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
.lvl-info { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
.lvl-debug { background: rgba(52, 211, 153, 0.2); color: #34d399; }

.result-content {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.result-source {
  color: #667eea;
  font-weight: bold;
  font-size: 0.75rem;
}

.result-message {
  color: #eee;
  flex: 1;
  font-size: 0.875rem;
}

.result-file {
  color: #666;
  font-size: 0.7rem;
  font-family: monospace;
}

.no-results {
  text-align: center;
  padding: 2rem;
  color: #888;
}
</style>
