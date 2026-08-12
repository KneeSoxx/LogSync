<template>
  <div class="timeline-container">
    <div class="timeline-header">
      <h2>Timeline View</h2>
      <div class="timeline-controls">
        <label>Correlation Window:</label>
        <select v-model="windowMs" @change="loadCorrelations">
          <option :value="100">100ms</option>
          <option :value="250">250ms</option>
          <option :value="500" selected>500ms</option>
          <option :value="1000">1000ms (1s)</option>
          <option :value="2000">2000ms (2s)</option>
        </select>
        <button @click="loadCorrelations" class="btn-secondary">Refresh</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading correlations...</div>

    <div v-else-if="correlationGroups.length === 0" class="empty-state">
      <p>No correlated events found. Upload logs from different sources to see correlations.</p>
    </div>

    <div v-else class="timeline-content">
      <!-- Event List -->
      <div class="events-panel">
        <h3>All Events ({{ totalEvents }})</h3>
        <div class="events-list" ref="eventsList">
          <div 
            v-for="(event, idx) in sortedEvents" 
            :key="idx"
            class="event-item"
            :class="'source-' + getFileSource(event.file)"
            @click="selectEvent(event)"
          >
            <span class="event-time">{{ formatTimestamp(event.timestamp) }}</span>
            <span class="event-source">{{ event.source }}</span>
            <span class="event-level" :class="'level-' + event.level.toLowerCase()">{{ event.level }}</span>
          </div>
        </div>
      </div>

      <!-- Correlation Groups -->
      <div class="groups-panel">
        <h3>Correlation Groups ({{ correlationGroups.length }} groups)</h3>
        <div class="groups-list">
          <div 
            v-for="(group, groupIdx) in correlationGroups" 
            :key="group.group_id"
            class="group-card"
            @click="selectGroup(group)"
          >
            <div class="group-header">
              <span class="group-id">{{ group.group_id }}</span>
              <span class="group-meta">{{ group.event_count }} events • {{ formatTimeSpan(group.time_span_ms) }}ms</span>
            </div>
            <div class="group-events" ref="groupEventRefs">
              <div 
                v-for="(evt, evtIdx) in group.events" 
                :key="evtIdx"
                class="group-event-item"
                :class="'source-' + getFileSource(evt.file)"
                @click.stop="selectEvent(evt)"
              >
                <span class="event-time-small">{{ formatTimestampShort(evt.timestamp) }}</span>
                <span class="event-level-small" :class="'level-' + evt.level.toLowerCase()">{{ evt.level }}</span>
                <span class="event-message">{{ evt.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Event Details Panel -->
    <div v-if="selectedEvent" class="details-panel" @click.away="closeDetails">
      <div class="details-header">
        <h3>Event Details</h3>
        <button @click="closeDetails" class="btn-close">×</button>
      </div>
      <div class="details-content">
        <div class="detail-row">
          <span class="label">Timestamp:</span>
          <span class="value">{{ selectedEvent.timestamp }}</span>
        </div>
        <div class="detail-row">
          <span class="label">Source:</span>
          <span class="value">{{ selectedEvent.source }}</span>
        </div>
        <div class="detail-row">
          <span class="label">Level:</span>
          <span class="value" :class="'level-' + selectedEvent.level.toLowerCase()">{{ selectedEvent.level }}</span>
        </div>
        <div class="detail-row">
          <span class="label">File:</span>
          <span class="value">{{ selectedEvent.file || 'unknown' }}</span>
        </div>
        <div class="detail-row">
          <span class="label">Line:</span>
          <span class="value">{{ selectedEvent.line_number || 0 }}</span>
        </div>
        <div class="detail-row full-width">
          <span class="label">Message:</span>
          <span class="value">{{ selectedEvent.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'Timeline',
  data() {
    return {
      loading: false,
      windowMs: 500,
      correlationGroups: [],
      sortedEvents: [],
      selectedEvent: null,
      eventsListRef: null,
      groupEventRefs: []
    }
  },
  computed: {
    totalEvents() {
      return this.sortedEvents.length
    }
  },
  mounted() {
    this.loadCorrelations()
  },
  methods: {
    async loadCorrelations() {
      this.loading = true
      try {
        const response = await axios.get('/api/correlate', { params: { window_ms: this.windowMs } })
        this.correlationGroups = response.data.groups || []
        
        // Flatten all events for the event list
        this.sortedEvents = []
        for (const group of this.correlationGroups) {
          this.sortedEvents.push(...group.events)
        }
        // Sort by timestamp
        this.sortedEvents.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      } catch (error) {
        console.error('Failed to load correlations:', error)
      } finally {
        this.loading = false
      }
    },

    selectEvent(event) {
      this.selectedEvent = event
    },

    selectGroup(group) {
      // Auto-scroll to the group
      const refElement = this.$refs[`groupEventRefs`][0]
      if (refElement) {
        refElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    },

    closeDetails() {
      this.selectedEvent = null
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

    formatTimestampShort(timestamp) {
      try {
        const date = new Date(timestamp)
        return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
      } catch (e) {
        return '??'
      }
    },

    formatTimeSpan(ms) {
      if (ms < 1000) return `${ms}ms`
      return `${(ms / 1000).toFixed(2)}s`
    },

    getFileSource(filename) {
      // Extract simple identifier from filename
      return filename.split('.')[0].substring(0, 10)
    }
  }
}
</script>

<style scoped>
.timeline-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 250px);
  background: #1e1e30;
  border-radius: 8px;
  padding: 1rem;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.timeline-header h2 {
  font-size: 1.25rem;
  color: #fff;
}

.timeline-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.btn-secondary {
  background: #444;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-secondary:hover {
  background: #555;
}

.loading, .empty-state {
  text-align: center;
  padding: 3rem;
  color: #888;
}

.timeline-content {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 1rem;
  flex: 1;
  min-height: 400px;
}

.events-panel, .groups-panel {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 1rem;
  overflow-y: auto;
}

.events-panel h3, .groups-panel h3 {
  font-size: 0.875rem;
  color: #888;
  margin-bottom: 1rem;
}

.events-list {
  max-height: 400px;
  overflow-y: auto;
}

.event-item {
  display: grid;
  grid-template-columns: 90px 120px 80px 1fr;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid #333;
  cursor: pointer;
  transition: background 0.2s;
}

.event-item:hover {
  background: rgba(102, 126, 234, 0.1);
}

.source-socket-server .event-time { color: #fbbf24; }
.source-gui .event-time { color: #60a5fa; }
.source-runner .event-time { color: #4ade80; }
.source-external .event-time { color: #c084fc; }

.event-source { font-weight: bold; font-size: 0.75rem; }
.event-level { text-align: right; font-size: 0.75rem; }

.level-error { color: #f87171; }
.level-warning { color: #fbbf24; }
.level-info { color: #60a5fa; }
.level-debug { color: #34d399; }

.group-card {
  background: #2a2a40;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.group-card:hover {
  background: #333350;
}

.group-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #444;
}

.group-id {
  font-family: monospace;
  color: #667eea;
  font-size: 0.875rem;
}

.group-meta {
  font-size: 0.75rem;
  color: #888;
}

.group-events {
  max-height: 200px;
  overflow-y: auto;
}

.group-event-item {
  display: grid;
  grid-template-columns: 70px 60px 1fr;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid #333;
  cursor: pointer;
  transition: background 0.2s;
}

.group-event-item:hover {
  background: rgba(102, 126, 234, 0.15);
}

.event-time-small { color: #888; font-size: 0.75rem; }
.event-level-small { font-size: 0.75rem; }
.event-message { font-size: 0.8125rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.details-panel {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #1e1e30;
  border-top: 2px solid #667eea;
  padding: 1rem 2rem;
  z-index: 100;
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.details-header h3 {
  font-size: 1.125rem;
  color: #fff;
}

.btn-close {
  background: none;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  transition: color 0.2s;
}

.btn-close:hover {
  color: #fff;
}

.details-content {
  display: grid;
  gap: 0.75rem;
}

.detail-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 0.5rem;
}

.detail-row.full-width {
  grid-template-columns: 1fr;
}

.detail-row .label {
  color: #888;
  font-size: 0.875rem;
}

.detail-row .value {
  color: #eee;
  font-family: monospace;
  font-size: 0.875rem;
}

@media (max-width: 1024px) {
  .timeline-content {
    grid-template-columns: 1fr;
  }
  
  .event-item, .group-event-item {
    grid-template-columns: 1fr;
  }
  
  .event-item .timestamp,
  .event-item .source,
  .event-item .level,
  .group-event-item .time-short,
  .group-event-item .level-small,
  .group-event-item .message {
    display: none;
  }
}
</style>
