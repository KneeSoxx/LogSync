<template>
  <div class="correlation-view">
    <div class="view-header">
      <h2>Log Correlation</h2>
      <p class="subtitle">Find related events across multiple log sources (within {{ windowMs }}ms)</p>
    </div>

    <div class="controls-section">
      <div class="control-group">
        <label for="window-select">Correlation Window:</label>
        <select id="window-select" v-model="windowMs" @change="applyWindowChange">
          <option :value="100">100ms (Very Tight)</option>
          <option :value="250">250ms (Short)</option>
          <option :value="500" selected>500ms (Medium)</option>
          <option :value="1000">1000ms (1 second)</option>
          <option :value="2000">2000ms (2 seconds)</option>
        </select>
      </div>

      <div class="control-group">
        <label for="sources-select">Filter by Source:</label>
        <select id="sources-select" v-model="selectedSource" @change="applySourceFilter">
          <option value="">All Sources</option>
          <option v-for="source in uniqueSources" :key="source" :value="source">{{ source }}</option>
        </select>
      </div>

      <button @click="loadCorrelations" :disabled="loading" class="btn-primary">
        {{ loading ? 'Loading...' : 'Refresh Correlations' }}
      </button>
    </div>

    <div v-if="loading" class="loading-indicator">
      <div class="spinner"></div>
      <p>Analyzing log files...</p>
    </div>

    <div v-else-if="groups.length === 0 && !error" class="empty-state">
      <div class="empty-icon">🔍</div>
      <h3>No Correlated Events Found</h3>
      <p>This could mean:</p>
      <ul>
        <li>Upload logs from multiple sources that run simultaneously</li>
        <li>The time window is too small for your log patterns</li>
        <li>Logs don't have properly parsed timestamps</li>
      </ul>
    </div>

    <div v-else-if="error" class="error-state">
      <p class="error-message">{{ error }}</p>
    </div>

    <div v-else class="results-section">
      <div class="stats-bar">
        <span>Total Groups: {{ groups.length }}</span>
        <span>Total Events: {{ totalEvents }}</span>
        <span>Source Varieties: {{ uniqueSources.length }}</span>
      </div>

      <!-- Groups Grid -->
      <div class="groups-grid">
        <div 
          v-for="(group, idx) in filteredGroups" 
          :key="idx"
          class="group-card"
          @click="viewGroupDetails(group)"
        >
          <div class="card-header">
            <span class="group-number">#{{ idx + 1 }}</span>
            <span class="event-count">{{ group.events.length }} events</span>
            <span class="time-span">{{ formatTimeSpan(group.time_span_ms) }}</span>
          </div>

          <div class="events-preview">
            <div 
              v-for="(evt, evtIdx) in group.events.slice(0, 3)" 
              :key="evtIdx"
              class="preview-event"
              :class="'source-' + getPreviewSource(evt.file)"
            >
              <span class="time">{{ formatPreviewTime(evt.timestamp) }}</span>
              <span class="level" :class="'lvl-' + evt.level.toLowerCase()">{{ evt.level }}</span>
              <span class="msg">{{ truncateMessage(evt.message, 60) }}</span>
            </div>
            <div v-if="group.events.length > 3" class="more-events">
              +{{ group.events.length - 3 }} more events
            </div>
          </div>

          <button class="view-details-btn" @click.stop="viewGroupDetails(group)">
            View Details →
          </button>
        </div>
      </div>
    </div>

    <!-- Group Details Modal -->
    <div v-if="selectedGroup" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Correlation Group #{{ selectedGroup.group_id }}</h3>
          <button @click="closeModal" class="modal-close">×</button>
        </div>

        <div class="modal-body">
          <div class="group-summary">
            <p><strong>{{ selectedGroup.events.length }} events</strong> from <strong>{{ uniqueSourcesInGroup }}</strong> sources occurred within <strong>{{ formatTimeSpan(selectedGroup.time_span_ms) }}</strong></p>
          </div>

          <table class="events-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Source</th>
                <th>Level</th>
                <th>File</th>
                <th>Line</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(evt, idx) in selectedGroup.events" :key="idx">
                <td class="time-cell">{{ formatTimestamp(evt.timestamp) }}</td>
                <td class="source-cell">{{ evt.source }}</td>
                <td class="level-cell" :class="'lvl-' + evt.level.toLowerCase()">{{ evt.level }}</td>
                <td class="file-cell">{{ evt.file || 'unknown' }}</td>
                <td class="line-cell">{{ evt.line_number || '-' }}</td>
                <td class="message-cell">{{ truncateMessage(evt.message, 80) }}</td>
              </tr>
            </tbody>
          </table>

          <div class="event-timeline">
            <h4>Visual Timeline</h4>
            <div class="timeline-visual">
              <div 
                v-for="(evt, idx) in selectedGroup.events" 
                :key="idx"
                class="timeline-marker"
                :class="'source-' + getTimelineSource(evt.file)"
                @click="selectEventInModal(evt)"
              >
                <span class="marker-dot"></span>
                <span class="marker-label">{{ formatShortTime(evt.timestamp) }}</span>
                <span class="marker-source">{{ evt.source }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="closeModal" class="btn-secondary">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'CorrelationView',
  data() {
    return {
      loading: false,
      windowMs: 500,
      selectedSource: '',
      groups: [],
      error: null,
      uniqueSources: [],
      selectedGroup: null
    }
  },
  computed: {
    totalEvents() {
      return this.groups.reduce((sum, group) => sum + group.events.length, 0)
    },
    filteredGroups() {
      if (!this.selectedSource) return this.groups
      return this.groups.filter(g => g.events.some(e => e.source === this.selectedSource))
    }
  },
  mounted() {
    this.loadCorrelations()
  },
  methods: {
    async loadCorrelations() {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.get('/api/correlate', { params: { window_ms: this.windowMs } })
        
        this.groups = response.data.groups || []
        this.uniqueSources = [...new Set(this.groups.flatMap(g => g.events.map(e => e.source)))]
      } catch (err) {
        this.error = 'Failed to load correlations. Please check the server logs.'
        console.error(err)
      } finally {
        this.loading = false
      }
    },

    applyWindowChange() {
      this.loadCorrelations()
    },

    applySourceFilter() {
      // Filter would be applied in computed property
    },

    closeModal() {
      this.selectedGroup = null
    },

    viewGroupDetails(group) {
      this.selectedGroup = group
    },

    selectEventInModal(event) {
      console.log('Selected event:', event)
      // Could navigate to side-by-side viewer for this specific file/line
    },

    getPreviewSource(filename) {
      return filename.split('.')[0].substring(0, 3)
    },

    getTimelineSource(filename) {
      return filename.split('.')[0]
    },

    formatTimestamp(timestamp) {
      try {
        const date = new Date(timestamp)
        return date.toLocaleTimeString('en-US', { 
          hour: '2-digit', 
          minute: '2-digit', 
          second: '2-digit',
          fractionalSecondDigits: 3
        })
      } catch (e) {
        return timestamp
      }
    },

    formatPreviewTime(timestamp) {
      try {
        const date = new Date(timestamp)
        return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}.${date.getSeconds().toString().padStart(2, '0')}`
      } catch (e) {
        return '??'
      }
    },

    formatShortTime(timestamp) {
      try {
        const date = new Date(timestamp)
        return `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}.${date.getSeconds().toString().padStart(2, '0')}`
      } catch (e) {
        return '??'
      }
    },

    formatTimeSpan(ms) {
      if (ms === 0 || !ms) return '<1ms'
      if (ms < 1000) return `${ms}ms`
      return `${(ms / 1000).toFixed(2)}s`
    },

    truncateMessage(message, maxLength) {
      if (!message || message.length <= maxLength) return message
      return message.substring(0, maxLength) + '...'
    },

    uniqueSourcesInGroup() {
      return new Set(this.selectedGroup.events.map(e => e.source)).size
    }
  }
}
</script>

<style scoped>
.correlation-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 250px);
  background: #1e1e30;
  border-radius: 8px;
  padding: 1.5rem;
  overflow-y: auto;
}

.view-header {
  margin-bottom: 1.5rem;
}

.view-header h2 {
  font-size: 1.5rem;
  color: #fff;
  margin-bottom: 0.25rem;
}

.subtitle {
  color: #888;
  font-size: 0.875rem;
}

.controls-section {
  display: flex;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: #2a2a40;
  border-radius: 8px;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.control-group label {
  font-size: 0.75rem;
  color: #888;
  text-transform: uppercase;
}

.control-group select {
  background: #1a1a2e;
  color: white;
  border: 1px solid #444;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  font-size: 0.875rem;
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

.loading-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  color: #888;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #333;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state, .error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.error-message {
  color: #f87171;
  max-width: 500px;
}

.results-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stats-bar {
  display: flex;
  gap: 2rem;
  padding: 1rem;
  background: #2a2a40;
  border-radius: 8px;
  font-size: 0.875rem;
  color: #aaa;
}

.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1rem;
}

.group-card {
  background: #2a2a40;
  border-radius: 8px;
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.group-card:hover {
  background: #333350;
  border-color: #667eea;
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #444;
}

.group-number {
  font-family: monospace;
  color: #667eea;
  font-size: 1.25rem;
  font-weight: bold;
}

.event-count, .time-span {
  font-size: 0.75rem;
  color: #888;
}

.events-preview {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.preview-event {
  display: grid;
  grid-template-columns: 70px 60px 1fr;
  gap: 0.5rem;
  padding: 0.5rem;
  background: #1a1a2e;
  border-radius: 4px;
  font-size: 0.8125rem;
}

.preview-event .time { color: #888; }
.preview-event .level { font-weight: bold; text-align: right; }
.preview-event .msg { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.lvl-error { color: #f87171; }
.lvl-warning { color: #fbbf24; }
.lvl-info { color: #60a5fa; }
.lvl-debug { color: #34d399; }

.more-events {
  font-size: 0.875rem;
  color: #888;
  text-align: center;
}

.view-details-btn {
  width: 100%;
  background: transparent;
  border: 2px solid #667eea;
  color: #667eea;
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.2s;
}

.view-details-btn:hover {
  background: #667eea;
  color: white;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #1e1e30;
  border-radius: 12px;
  max-width: 900px;
  width: 95%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid #333;
}

.modal-header h3 {
  font-size: 1.25rem;
  color: #fff;
}

.modal-close {
  background: none;
  border: none;
  color: #888;
  font-size: 2rem;
  cursor: pointer;
  transition: color 0.2s;
}

.modal-close:hover {
  color: #fff;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.group-summary {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: #2a2a40;
  border-radius: 8px;
  color: #ccc;
}

.events-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1.5rem;
}

.events-table th, .events-table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #333;
}

.events-table th {
  background: #2a2a40;
  color: #888;
  font-size: 0.75rem;
  text-transform: uppercase;
}

.events-table tr:hover td {
  background: rgba(102, 126, 234, 0.1);
}

.time-cell { color: #888; font-family: monospace; }
.source-cell { font-weight: bold; }
.level-cell { font-size: 0.75rem; font-weight: bold; text-align: center; }
.file-cell, .line-cell { font-size: 0.8125rem; color: #aaa; }
.message-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.event-timeline {
  margin-top: 1.5rem;
}

.event-timeline h4 {
  font-size: 0.875rem;
  color: #888;
  margin-bottom: 1rem;
}

.timeline-visual {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 1rem;
  background: #1a1a2e;
  border-radius: 8px;
  overflow-x: auto;
}

.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 80px;
}

.timeline-marker:hover {
  background: rgba(102, 126, 234, 0.2);
}

.marker-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #666;
}

.timeline-marker.socket-server .marker-dot { background: #fbbf24; }
.timeline-marker.gui .marker-dot { background: #60a5fa; }
.timeline-marker.runner .marker-dot { background: #4ade80; }
.timeline-marker.external .marker-dot { background: #c084fc; }

.marker-label {
  font-size: 0.7rem;
  color: #888;
}

.marker-source {
  font-size: 0.65rem;
  color: #aaa;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid #333;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary {
  background: #444;
  color: white;
  border: none;
  padding: 0.625rem 1.25rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
}

.btn-secondary:hover {
  background: #555;
}

@media (max-width: 768px) {
  .groups-grid {
    grid-template-columns: 1fr;
  }
  
  .modal-content {
    max-height: 95vh;
  }
  
  .events-table th, .events-table td {
    padding: 0.5rem;
    font-size: 0.75rem;
  }
}
</style>
