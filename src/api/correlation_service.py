"""Correlation service for grouping related log events."""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict


class CorrelationService:
    """Service for correlating log events within time windows."""
    
    DEFAULT_WINDOW_MS = 500
    
    def __init__(self, window_ms: int = None):
        self.window_ms = window_ms or self.DEFAULT_WINDOW_MS
        self.window_delta = timedelta(milliseconds=self.window_ms)
    
    def correlate_events(self, events: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group events that occur within the configured time window."""
        if not events:
            return []
        
        valid_events = [e for e in events if e.get('timestamp')]
        if not valid_events:
            return []
        
        sorted_events = sorted(valid_events, key=lambda x: x['timestamp'])
        groups = self._sliding_window_group(sorted_events)
        
        return groups
    
    def _sliding_window_group(self, events: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group events using sliding window algorithm."""
        if not events:
            return []
        
        groups = []
        current_group = [events[0]]
        
        for event in events[1:]:
            last_event = current_group[-1]
            
            within_window = False
            for group_event in current_group:
                time_diff = abs((event['timestamp'] - group_event['timestamp']).total_seconds() * 1000)
                if time_diff <= self.window_ms:
                    within_window = True
                    break
            
            if within_window:
                closest_idx = min(
                    range(len(current_group)),
                    key=lambda i: abs((event['timestamp'] - current_group[i]['timestamp']).total_seconds() * 1000)
                )
                current_group.insert(closest_idx + 1, event)
            else:
                groups.append(current_group)
                current_group = [event]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def find_correlated_events(self, events: List[Dict[str, Any]], reference_event: Dict[str, Any], window_ms: int = None) -> List[Dict[str, Any]]:
        """Find all events correlated to a specific reference event."""
        if not events or not reference_event:
            return []
        
        target_time = reference_event.get('timestamp')
        if not target_time:
            return []
        
        target_dt = datetime.fromisoformat(target_time.replace('Z', '+00:00')) if 'Z' in str(target_time) else datetime.fromisoformat(target_time)
        
        effective_window = (window_ms or self.window_ms) / 1000.0
        
        correlated = []
        for event in events:
            if not event.get('timestamp'):
                continue
            
            try:
                event_dt = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) if 'Z' in str(event['timestamp']) else datetime.fromisoformat(event['timestamp'])
                
                time_diff = abs((event_dt - target_dt).total_seconds())
                if time_diff <= effective_window:
                    correlated.append(event)
            except (ValueError, TypeError):
                continue
        
        correlated.append(reference_event)
        
        return correlated
    
    def get_timeline_events(self, events: List[Dict[str, Any]], start_time: datetime = None, end_time: datetime = None) -> Tuple[List[Dict[str, Any]], float]:
        """Get all events within a time range for timeline display."""
        if not events:
            return [], 0
        
        filtered = []
        for event in events:
            ts = event.get('timestamp')
            if not ts:
                continue
            
            try:
                event_dt = datetime.fromisoformat(ts.replace('Z', '+00:00')) if 'Z' in str(ts) else datetime.fromisoformat(ts)
                
                if start_time and event_dt < start_time:
                    continue
                if end_time and event_dt > end_time:
                    continue
                
                filtered.append(event)
            except (ValueError, TypeError):
                continue
        
        if not filtered:
            return [], 0
        
        timestamps = [datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) if 'Z' in str(e['timestamp']) else datetime.fromisoformat(e['timestamp']) for e in filtered]
        min_time = min(timestamps)
        max_time = max(timestamps)
        
        time_span_ms = (max_time - min_time).total_seconds() * 1000
        
        return filtered, time_span_ms
    
    def extract_unique_sources(self, events: List[Dict[str, Any]]) -> List[str]:
        """Extract unique source names from events."""
        sources = set()
        for event in events:
            if event.get('source'):
                sources.add(event['source'])
        return sorted(list(sources))


_correlation_service = None

def get_correlation_service(window_ms: int = None) -> CorrelationService:
    """Get or create the global correlation service."""
    global _correlation_service
    if _correlation_service is None:
        _correlation_service = CorrelationService(window_ms=window_ms)
    return _correlation_service


def reset_correlation_service():
    """Reset the global correlation service (useful for testing)."""
    global _correlation_service
    _correlation_service = None
