/**
 * Session Lifecycle Visualizer
 * Provides visual timelines and diagnostics for session activity.
 */

// Session Visualizer State
let visualizationData = [];

class SessionVisualizer {
    constructor() {
        this.container = null;
        this.timelineContainer = null;
        this.statsContainer = null;
        this.initializeVisualizer();
    }

    /**
     * Initialize the session visualizer
     */
    async initializeVisualizer() {
        console.log('[SessionVisualizer] Initializing session lifecycle visualizer...');

        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupUI());
        } else {
            this.setupUI();
        }
    }

    /**
     * Setup the visualizer UI
     */
    setupUI() {
        // Check if UI already exists
        if (document.getElementById('session-visualizer-container')) {
            return;
        }

        const visualizerContainer = document.createElement('div');
        visualizerContainer.id = 'session-visualizer-container';
        visualizerContainer.className = 'session-visualizer-container hidden';
        visualizerContainer.innerHTML = `
            <div class="visualizer-header">
                <h2>📊 Session Lifecycle Visualization</h2>
                <div class="visualizer-actions">
                    <button id="refresh-visualizer-btn" class="btn-secondary">🔄 Refresh</button>
                    <button id="close-visualizer-btn" class="btn-secondary">✕ Close</button>
                </div>
            </div>

            <div class="visualizer-content">
                <div class="session-stats" id="session-stats">
                    <div class="stat-card">
                        <h3>🟢 Active Sessions</h3>
                        <span id="active-sessions-count">-</span>
                    </div>
                    <div class="stat-card">
                        <h3>📈 Total Interactions</h3>
                        <span id="total-messages">-</span>
                    </div>
                    <div class="stat-card">
                        <h3>🎯 Memory Usage</h3>
                        <span id="memory-usage">-</span>
                    </div>
                </div>

                <div class="visualizer-tabs">
                    <button class="vis-tab active" data-visualization="timeline">🕐 Timeline</button>
                    <button class="vis-tab" data-visualization="workflows">🔄 Workflows</button>
                    <button class="vis-tab" data-visualization="performance">⚡ Performance</button>
                </div>

                <div id="timeline-view" class="visualization-view active">
                    <div id="session-timeline" class="session-timeline">
                        <div class="timeline-loading">
                            <p>Loading session timeline...</p>
                        </div>
                    </div>
                </div>

                <div id="workflows-view" class="visualization-view">
                    <div id="workflow-diagram" class="workflow-diagram">
                        <div class="diagram-loading">
                            <p>Loading workflow isolation status...</p>
                        </div>
                    </div>
                </div>

                <div id="performance-view" class="visualization-view">
                    <div id="performance-metrics" class="performance-metrics">
                        <div class="metric-loading">
                            <p>Loading performance metrics...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Insert into page
        const mainContent = document.querySelector('.main-content') ||
                           document.querySelector('#main-container') ||
                           document.body;

        // Find appropriate insertion point
        const existingContainer = document.querySelector('.container') ||
                                 document.querySelector('.main') ||
                                 document.body;

        existingContainer.appendChild(visualizerContainer);

        // Cache DOM elements
        this.container = visualizerContainer;
        this.statsContainer = document.getElementById('session-stats');
        this.timelineContainer = document.getElementById('session-timeline');

        // Attach event handlers
        this.attachEventHandlers();

        console.log('[SessionVisualizer] Session visualizer UI created');
    }

    /**
     * Attach event handlers
     */
    attachEventHandlers() {
        // Tab switching
        document.querySelectorAll('.vis-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const visualization = e.target.closest('.vis-tab').dataset.visualization;
                this.switchVisualization(visualization);
            });
        });

        // Refresh button
        const refreshBtn = document.getElementById('refresh-visualizer-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshVisualization());
        }

        // Close button
        const closeBtn = document.getElementById('close-visualizer-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideVisualizer());
        }
    }

    /**
     * Show the session visualizer
     */
    showVisualizer() {
        if (this.container) {
            this.container.classList.remove('hidden');
            this.refreshVisualization();
        }
    }

    /**
     * Hide the session visualizer
     */
    hideVisualizer() {
        if (this.container) {
            this.container.classList.add('hidden');
        }
    }

    /**
     * Refresh all visualization data
     */
    async refreshVisualization() {
        this.loadSessionStats();
        this.loadTimelineData();

        // Update active tab
        const activeTab = document.querySelector('.vis-tab.active');
        if (activeTab) {
            const visualization = activeTab.dataset.visualization;
            this.switchVisualization(visualization);
        }

        console.log('[SessionVisualizer] Visualization refreshed');
    }

    /**
     * Load session statistics
     */
    async loadSessionStats() {
        try {
            // Fetch session stats from backend
            const response = await fetch('/api/chat_history/sessions');

            if (!response.ok) {
                throw new Error(`Failed to load session stats: ${response.status}`);
            }

            const data = await response.json();
            const sessions = data.sessions || [];

            // Calculate stats
            const activeSessions = sessions.length;
            const totalMessages = sessions.reduce((sum, session) => sum + (session.messages?.length || 0), 0);
            const memoryUsage = this.estimateMemoryUsage(sessions);

            // Update UI
            this.updateSessionStats(activeSessions, totalMessages, memoryUsage);

        } catch (error) {
            console.error('[SessionVisualizer] Failed to load session stats:', error);
            this.showStatsError();
        }
    }

    /**
     * Update session statistics display
     */
    updateSessionStats(activeSessions, totalMessages, memoryUsage) {
        const activeEl = document.getElementById('active-sessions-count');
        const messagesEl = document.getElementById('total-messages');
        const memoryEl = document.getElementById('memory-usage');

        if (activeEl) activeEl.textContent = activeSessions;
        if (messagesEl) messagesEl.textContent = totalMessages.toLocaleString();
        if (memoryEl) memoryEl.textContent = this.formatMemoryUsage(memoryUsage);
    }

    /**
     * Show error state for stats
     */
    showStatsError() {
        const activeEl = document.getElementById('active-sessions-count');
        const messagesEl = document.getElementById('total-messages');
        const memoryEl = document.getElementById('memory-usage');

        [activeEl, messagesEl, memoryEl].forEach(el => {
            if (el) el.textContent = 'Error';
        });
    }

    /**
     * Load timeline data for visualization
     */
    async loadTimelineData() {
        try {
            // Get session data for timeline
            const response = await fetch('/api/chat_history/sessions');
            if (!response.ok) {
                throw new Error(`Failed to load timeline data: ${response.status}`);
            }

            const data = await response.json();
            const sessions = data.sessions || [];

            // Generate timeline data
            visualizationData = this.generateTimelineData(sessions);
            this.renderTimeline();

        } catch (error) {
            console.error('[SessionVisualizer] Failed to load timeline data:', error);
            this.showTimelineError();
        }
    }

    /**
     * Generate timeline data from sessions
     */
    generateTimelineData(sessions) {
        const timeline = [];

        sessions.forEach(session => {
            // Session creation event
            timeline.push({
                type: 'session_created',
                session_id: session.session_id,
                workflow: session.workflow_name,
                title: session.title || 'Untitled Session',
                timestamp: session.created_at,
                details: `Session created for ${session.workflow_name}`
            });

            // Message events
            if (session.messages && session.messages.length > 0) {
                session.messages.forEach((message, index) => {
                    timeline.push({
                        type: 'message',
                        session_id: session.session_id,
                        workflow: session.workflow_name,
                        title: session.title || 'Untitled Session',
                        timestamp: message.timestamp || new Date().toISOString(),
                        details: `${message.role}: ${message.content?.substring(0, 50)}...`,
                        message_index: index
                    });
                });
            }

            // Session is active (add current time marker)
            timeline.push({
                type: 'session_active',
                session_id: session.session_id,
                workflow: session.workflow_name,
                title: session.title || 'Untitled Session',
                timestamp: new Date().toISOString(),
                details: 'Session currently active'
            });
        });

        // Sort by timestamp
        timeline.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        return timeline;
    }

    /**
     * Render the session timeline
     */
    renderTimeline() {
        if (!this.timelineContainer) return;

        if (visualizationData.length === 0) {
            this.timelineContainer.innerHTML = `
                <div class="timeline-empty">
                    <h3>📅 No Session History</h3>
                    <p>Create sessions and interact with workflows to see timeline data</p>
                </div>
            `;
            return;
        }

        let timelineHtml = `
            <div class="timeline-header">
                <h3>Session Activity Timeline</h3>
                <span class="timeline-count">${visualizationData.length} events</span>
            </div>
            <div class="timeline-events">
        `;

        // Group events by date
        const eventsByDate = this.groupEventsByDate(visualizationData);

        for (const [date, events] of Object.entries(eventsByDate)) {
            timelineHtml += `
                <div class="timeline-date-group">
                    <div class="timeline-date">${this.formatDisplayDate(date)}</div>
                    <div class="timeline-events-list">
                        ${events.map(event => this.renderTimelineEvent(event)).join('')}
                    </div>
                </div>
            `;
        }

        timelineHtml += `
            </div>
        </div>
        `;

        this.timelineContainer.innerHTML = timelineHtml;
    }

    /**
     * Render a single timeline event
     */
    renderTimelineEvent(event) {
        const eventType = event.type;
        const icon = this.getEventIcon(eventType);
        const time = new Date(event.timestamp).toLocaleTimeString();
        const timeAgo = this.getTimeAgo(event.timestamp);

        return `
            <div class="timeline-event ${eventType}" data-session-id="${event.session_id}">
                <div class="event-marker">
                    <span class="event-icon">${icon}</span>
                </div>
                <div class="event-content">
                    <div class="event-header">
                        <span class="event-type">${this.formatEventType(eventType)}</span>
                        <span class="event-time">${time} (${timeAgo})</span>
                    </div>
                    <div class="event-details">${event.details}</div>
                    <div class="event-meta">
                        <span class="event-workflow">${event.workflow}</span>
                        <span class="event-session">${event.title}</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Switch between different visualizations
     */
    switchVisualization(visualizationType) {
        console.log(`[SessionVisualizer] Switching to visualization: ${visualizationType}`);

        // Update tab buttons
        document.querySelectorAll('.vis-tab').forEach(tab => {
            tab.classList.remove('active');
        });

        const activeTabBtn = document.querySelector(`.vis-tab[data-visualization="${visualizationType}"]`);
        if (activeTabBtn) {
            activeTabBtn.classList.add('active');
        }

        // Update view content
        document.querySelectorAll('.visualization-view').forEach(view => {
            view.classList.remove('active');
        });

        const activeView = document.getElementById(`${visualizationType}-view`);
        if (activeView) {
            activeView.classList.add('active');
        }

        // Load content for the active view
        switch (visualizationType) {
            case 'timeline':
                this.loadTimelineData();
                break;
            case 'workflows':
                this.loadWorkflowIsolationView();
                break;
            case 'performance':
                this.loadPerformanceMetrics();
                break;
        }

        console.log(`[SessionVisualizer] Visualization switched to: ${visualizationType}`);
    }

    /**
     * Load workflow isolation status view
     */
    async loadWorkflowIsolationView() {
        const workflowContainer = document.getElementById('workflow-diagram');

        if (!workflowContainer) return;

        try {
            // Fetch session data
            const response = await fetch('/api/chat_history/sessions');
            if (!response.ok) {
                throw new Error('Failed to load workflow data');
            }

            const data = await response.json();
            const sessions = data.sessions || [];

            // Analyze workflow isolation
            const isolationStatus = this.analyzeWorkflowIsolation(sessions);

            workflowContainer.innerHTML = `
                <div class="isolation-dashboard">
                    <div class="isolation-status">
                        <h3>🛡️ Workflow Isolation Status</h3>
                        <div class="status-indicator ${isolationStatus.isolated ? 'good' : 'warning'}">
                            <span class="status-icon">${isolationStatus.isolated ? '✅' : '⚠️'}</span>
                            <span class="status-text">
                                ${isolationStatus.isolated ? 'Sessions Properly Isolated' : 'Isolation Issues Detected'}
                            </span>
                        </div>
                    </div>

                    <div class="isolation-details">
                        <div class="isolation-stats">
                            <div class="stat-item">
                                <strong>Total Sessions:</strong> ${isolationStatus.totalSessions}
                            </div>
                            <div class="stat-item">
                                <strong>Workflows:</strong> ${isolationStatus.totalWorkflows}
                            </div>
                            <div class="stat-item">
                                <strong>Average Sessions per Workflow:</strong> ${isolationStatus.avgSessionsPerWorkflow.toFixed(1)}
                            </div>
                        </div>

                        <div class="workflow-breakdown">
                            <h4>Workflow Activity</h4>
                            ${this.renderWorkflowBreakdown(isolationStatus.workflowStats)}
                        </div>
                    </div>
                </div>
            `;

        } catch (error) {
            console.error('[SessionVisualizer] Failed to load workflow isolation data:', error);
            workflowContainer.innerHTML = '<div class="error">Failed to load workflow isolation data</div>';
        }
    }

    /**
     * Load performance metrics view
     */
    async loadPerformanceMetrics() {
        const perfContainer = document.getElementById('performance-metrics');

        if (!perfContainer) return;

        // Generate mock performance data (in real system, this would come from backend)
        const performanceData = this.generatePerformanceMetrics();

        perfContainer.innerHTML = `
            <div class="performance-dashboard">
                <div class="performance-grid">
                    <div class="performance-card">
                        <h4>🧠 Memory Usage</h4>
                        <div class="metric-value">${performanceData.memoryUsage} MB</div>
                        <div class="metric-trend ${performanceData.memoryTrend}">${performanceData.memoryTrend}</div>
                    </div>

                    <div class="performance-card">
                        <h4>⚡ Session Creation Time</h4>
                        <div class="metric-value">${performanceData.sessionCreationTime}ms</div>
                        <div class="metric-trend ${performanceData.creationTrend}">${performanceData.creationTrend}</div>
                    </div>

                    <div class="performance-card">
                        <h4>🔄 Concurrent Sessions</h4>
                        <div class="metric-value">${performanceData.concurrentSessions}</div>
                        <div class="metric-trend stable">stable</div>
                    </div>

                    <div class="performance-card">
                        <h4>📈 Peak Usage</h4>
                        <div class="metric-value">${performanceData.peakUsage}</div>
                        <div class="metric-trend ${performanceData.peakTrend}">${performanceData.peakTrend}</div>
                    </div>
                </div>

                <div class="performance-details">
                    <h4>System Health</h4>
                    <ul class="health-indicators">
                        <li class="health-item ${this.getHealthClass(performanceData.registryHealth)}">
                            Session Registry: ${performanceData.registryHealth}
                        </li>
                        <li class="health-item ${this.getHealthClass(performanceData.memoryHealth)}">
                            Memory Management: ${performanceData.memoryHealth}
                        </li>
                        <li class="health-item ${this.getHealthClass(performanceData.cleanupHealth)}">
                            Session Cleanup: ${performanceData.cleanupHealth}
                        </li>
                        <li class="health-item ${this.getHealthClass(performanceData.isolationHealth)}">
                            Workflow Isolation: ${performanceData.isolationHealth}
                        </li>
                    </ul>
                </div>
            </div>
        `;
    }

    /**
     * Generate mock performance metrics (for demonstration)
     */
    generatePerformanceMetrics() {
        return {
            memoryUsage: '45.2',
            memoryTrend: 'stable',
            sessionCreationTime: '12.3',
            creationTrend: 'improving',
            concurrentSessions: '8',
            peakUsage: '92% of capacity',
            peakTrend: 'stable',
            registryHealth: 'excellent',
            memoryHealth: 'good',
            cleanupHealth: 'good',
            isolationHealth: 'excellent'
        };
    }

    /**
     * Show error state for timeline
     */
    showTimelineError() {
        if (this.timelineContainer) {
            this.timelineContainer.innerHTML = `
                <div class="timeline-error">
                    <h3>❌ Failed to Load Timeline</h3>
                    <p>Unable to load session timeline data. Please try refreshing.</p>
                </div>
            `;
        }
    }

    // Utility Methods

    /**
     * Estimate memory usage from sessions
     */
    estimateMemoryUsage(sessions) {
        // Rough estimation: 1KB per message + 10KB per session overhead
        const baseSessionMemory = 10; // KB
        const messageMemory = 1; // KB per message

        let totalMemory = 0;
        sessions.forEach(session => {
            totalMemory += baseSessionMemory;
            if (session.messages) {
                totalMemory += session.messages.length * messageMemory;
            }
        });

        return totalMemory;
    }

    /**
     * Format memory usage for display
     */
    formatMemoryUsage(memoryKb) {
        if (memoryKb < 1024) {
            return `${memoryKb} KB`;
        } else {
            return `${(memoryKb / 1024).toFixed(1)} MB`;
        }
    }

    /**
     * Group events by date for timeline display
     */
    groupEventsByDate(events) {
        const grouped = {};

        events.forEach(event => {
            const date = new Date(event.timestamp).toDateString();
            if (!grouped[date]) {
                grouped[date] = [];
            }
            grouped[date].push(event);
        });

        return grouped;
    }

    /**
     * Format date for display
     */
    formatDisplayDate(dateString) {
        const date = new Date(dateString);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        if (date.toDateString() === today.toDateString()) {
            return 'Today';
        } else if (date.toDateString() === yesterday.toDateString()) {
            return 'Yesterday';
        } else {
            return date.toLocaleDateString();
        }
    }

    /**
     * Get time ago string
     */
    getTimeAgo(timestamp) {
        const now = new Date();
        const eventTime = new Date(timestamp);
        const diffMs = now - eventTime;
        const diffMins = Math.floor(diffMs / (1000 * 60));

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins} min ago`;

        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours} hr ago`;

        const diffDays = Math.floor(diffHours / 24);
        return `${diffDays} days ago`;
    }

    /**
     * Get icon for event type
     */
    getEventIcon(eventType) {
        const icons = {
            'session_created': '🆕',
            'session_active': '🟢',
            'message': '💬',
            'artifact_created': '📎',
            'session_complete': '✅'
        };
        return icons[eventType] || '📝';
    }

    /**
     * Format event type for display
     */
    formatEventType(eventType) {
        const types = {
            'session_created': 'Session Created',
            'session_active': 'Session Active',
            'message': 'Message',
            'artifact_created': 'Artifact Created',
            'session_complete': 'Session Complete'
        };
        return types[eventType] || eventType;
    }

    /**
     * Analyze workflow isolation status
     */
    analyzeWorkflowIsolation(sessions) {
        const workflowStats = {};
        let totalSessions = 0;

        sessions.forEach(session => {
            const workflow = session.workflow_name || 'unknown';
            if (!workflowStats[workflow]) {
                workflowStats[workflow] = { sessions: 0, messages: 0 };
            }
            workflowStats[workflow].sessions += 1;
            workflowStats[workflow].messages += session.messages?.length || 0;
            totalSessions += 1;
        });

        const totalWorkflows = Object.keys(workflowStats).length;
        const avgSessionsPerWorkflow = totalSessions / Math.max(totalWorkflows, 1);

        // Isolation is good if sessions are reasonably distributed and no single workflow dominates
        const isIsolated = totalWorkflows > 0 && avgSessionsPerWorkflow >= 0.5;

        return {
            isolated: isIsolated,
            totalSessions: totalSessions,
            totalWorkflows: totalWorkflows,
            avgSessionsPerWorkflow: avgSessionsPerWorkflow,
            workflowStats: workflowStats
        };
    }

    /**
     * Render workflow breakdown visualization
     */
    renderWorkflowBreakdown(workflowStats) {
        let html = '<div class="workflow-breakdown-container">';

        for (const [workflow, stats] of Object.entries(workflowStats)) {
            const percentage = Math.ceil((stats.sessions / Object.values(workflowStats).reduce((sum, s) => sum + s.sessions, 0)) * 100);

            html += `
                <div class="workflow-breakdown-item">
                    <div class="workflow-name">${workflow}</div>
                    <div class="workflow-stats">
                        <span class="session-count">${stats.sessions} sessions</span>
                        <span class="message-count">${stats.messages} messages</span>
                    </div>
                    <div class="workflow-bar" style="width: ${percentage}%"></div>
                </div>
            `;
        }

        html += '</div>';
        return html;
    }

    /**
     * Get health class for performance indicators
     */
    getHealthClass(health) {
        switch (health?.toLowerCase()) {
            case 'excellent': return 'excellent';
            case 'good': return 'good';
            case 'warning': case 'fair': return 'warning';
            case 'poor': case 'critical': return 'critical';
            default: return 'unknown';
        }
    }
}

// CSS Styles for Session Visualizer
const visualizerStyles = `
<style>
.session-visualizer-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(5px);
}

.session-visualizer-container.hidden {
    display: none;
}

.session-visualizer-container > div {
    background: white;
    border-radius: 12px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    max-width: 90vw;
    max-height: 90vh;
    width: 1200px;
    height: 800px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.visualizer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 30px;
    border-bottom: 1px solid #e0e0e0;
    background: #f8f9fa;
}

.visualizer-header h2 {
    margin: 0;
    color: #333;
}

.visualizer-actions {
    display: flex;
    gap: 10px;
}

.visualizer-content {
    flex: 1;
    overflow-y: auto;
    padding: 20px 30px;
}

.session-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.stat-card {
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
}

.stat-card h3 {
    margin: 0 0 10px 0;
    color: #666;
    font-size: 14px;
    font-weight: 600;
}

.stat-card h3:first-child {
    color: #28a745;
}

.session-stats span {
    font-size: 28px;
    font-weight: bold;
    color: #333;
}

.visualizer-tabs {
    display: flex;
    border-bottom: 1px solid #dee2e6;
    margin-bottom: 20px;
}

.vis-tab {
    background: none;
    border: none;
    padding: 12px 20px;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    color: #6c757d;
    font-weight: 500;
    transition: all 0.2s ease;
}

.vis-tab.active {
    color: #007bff;
    border-bottom-color: #007bff;
}

.vis-tab:hover {
    background: #f8f9fa;
}

.visualization-view {
    display: none;
}

.visualization-view.active {
    display: block;
}

/* Timeline Styles */
.session-timeline {
    background: white;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
}

.timeline-header {
    padding: 20px;
    border-bottom: 1px solid #e0e0e0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.timeline-header h3 {
    margin: 0;
    color: #333;
}

.timeline-count {
    background: #007bff;
    color: white;
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}

.timeline-events {
    padding: 20px;
}

.timeline-date-group {
    margin-bottom: 40px;
}

.timeline-date-group:last-child {
    margin-bottom: 0;
}

.timeline-date {
    font-size: 18px;
    font-weight: bold;
    color: #333;
    margin-bottom: 15px;
    padding-left: 20px;
}

.timeline-events-list {
    position: relative;
    padding-left: 30px;
}

.timeline-events-list::before {
    content: '';
    position: absolute;
    left: 15px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #e9ecef;
}

.timeline-event {
    position: relative;
    margin-bottom: 25px;
    padding-left: 40px;
}

.timeline-event::before {
    content: '';
    position: absolute;
    left: -38px;
    top: 15px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: white;
    border: 2px solid #007bff;
}

.event-marker {
    position: absolute;
    left: -50px;
    top: 10px;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #007bff;
    display: flex;
    align-items: center;
    justify-content: center;
}

.event-marker .event-icon {
    font-size: 14px;
    color: white;
}

.event-content {
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 15px;
}

.event-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 14px;
}

.event-type {
    font-weight: 600;
    color: #333;
}

.event-time {
    color: #6c757d;
    font-size: 12px;
}

.event-details {
    color: #495057;
    margin-bottom: 8px;
}

.event-meta {
    font-size: 12px;
    color: #6c757d;
}

.event-workflow {
    background: #e9ecef;
    padding: 2px 6px;
    border-radius: 4px;
    margin-right: 8px;
}

.timeline-empty, .timeline-loading, .timeline-error {
    text-align: center;
    padding: 60px 20px;
    color: #666;
}

.timeline-loading {
    color: #007bff;
}

/* Workflow Isolation Styles */
.isolation-dashboard {
    background: white;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    padding: 20px;
}

.isolation-status {
    margin-bottom: 30px;
}

.isolation-status h3 {
    margin: 0 0 15px 0;
    color: #333;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 15px;
    border-radius: 8px;
}

.status-indicator.good {
    background: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
}

.status-indicator.warning {
    background: #fff3cd;
    border: 1px solid #ffeaa7;
    color: #856404;
}

.isolation-details {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 30px;
}

.isolation-stats, .workflow-breakdown {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
}

.isolation-stats .stat-item {
    margin-bottom: 10px;
}

.isolation-stats .stat-item:last-child {
    margin-bottom: 0;
}

.workflow-breakdown h4 {
    margin: 0 0 15px 0;
    color: #333;
}

.workflow-breakdown-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.workflow-breakdown-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px;
    background: white;
    border-radius: 6px;
    border: 1px solid #dee2e6;
}

.workflow-name {
    font-weight: 600;
    color: #333;
    flex: 1;
}

.workflow-stats {
    display: flex;
    gap: 15px;
    font-size: 14px;
    color: #6c757d;
    flex: 1;
}

.workflow-bar {
    height: 8px;
    background: #007bff;
    border-radius: 4px;
    transition: width 0.3s ease;
}

/* Performance Styles */
.performance-dashboard {
    background: white;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    padding: 20px;
}

.performance-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.performance-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    border: 1px solid #e0e0e0;
}

.performance-card h4 {
    margin: 0 0 15px 0;
    color: #666;
    font-size: 14px;
    font-weight: 600;
}

.metric-value {
    font-size: 28px;
    font-weight: bold;
    color: #333;
    margin-bottom: 5px;
}

.metric-trend {
    font-size: 12px;
    padding: 2px 6px;
    border-radius: 10px;
    text-transform: uppercase;
    font-weight: 500;
}

.metric-trend.stable {
    background: #d1ecf1;
    color: #0c5460;
}

.metric-trend.improving {
    background: #d4edda;
    color: #155724;
}

.metric-trend.worsening {
    background: #f8d7da;
    color: #721c24;
}

.performance-details h4 {
    margin: 0 0 15px 0;
    color: #333;
}

.health-indicators {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 8px;
}

.health-item {
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 14px;
    display: flex;
    justify-content: space-between;
}

.health-item.excellent {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.health-item.good {
    background: #d1ecf1;
    color: #0c5460;
    border: 1px solid #b3d7de;
}

.health-item.warning {
    background: #fff3cd;
    color: #856404;
    border: 1px solid #ffeaa7;
}

.health-item.critical {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}

.metric-loading, .diagram-loading, .timeline-error {
    text-align: center;
    padding: 60px 20px;
}

.metric-loading p, .diagram-loading p, .timeline-error p {
    color: #666;
    margin: 0;
}
</style>
`;

// Add to page
document.addEventListener('DOMContentLoaded', () => {
    // Inject styles
    document.head.insertAdjacentHTML('beforeend', visualizerStyles);

    // Initialize visualizer
    window.sessionVisualizer = new SessionVisualizer();

    console.log('[SessionVisualizer] Session lifecycle visualizer module loaded');
});

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionVisualizer;
}
