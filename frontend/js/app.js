/**
 * ServiceNow AI Automation — Dashboard JavaScript
 *
 * Handles API communication, data rendering, auto-refresh,
 * and real-time toast notifications.
 */

// ── Configuration ────────────────────────────────────────────────────────────
const API_BASE = '';  // Same origin
const REFRESH_INTERVAL_MS = 10000;  // Auto-refresh every 10 seconds

let refreshTimer = null;

// ── Initialization ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    refreshAll();
    startAutoRefresh();
});

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL_MS);
}

async function refreshAll() {
    await Promise.all([
        loadStats(),
        loadTickets(),
        loadRuns(),
        loadSchedule(),
    ]);
}

// ── API Helpers ──────────────────────────────────────────────────────────────
async function apiFetch(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (err) {
        console.error(`API error (${endpoint}):`, err);
        return null;
    }
}

async function apiPost(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (err) {
        console.error(`API POST error (${endpoint}):`, err);
        return null;
    }
}

// ── Load Stats ───────────────────────────────────────────────────────────────
async function loadStats() {
    const stats = await apiFetch('/api/tickets/stats');
    if (!stats) return;

    animateNumber('stat-total', stats.total_processed);
    animateNumber('stat-notified', stats.total_notified);
    animateNumber('stat-failed', stats.total_failed);
    animateNumber('stat-lobs', Object.keys(stats.lob_breakdown).length);

    // Update LOB filter dropdown
    updateLobFilter(Object.keys(stats.lob_breakdown));

    // Update LOB chart
    renderLobChart(stats.lob_breakdown);
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    const current = parseInt(el.textContent) || 0;

    if (current === target) return;

    const duration = 600;
    const startTime = performance.now();

    function step(timestamp) {
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        const value = Math.round(current + (target - current) * eased);
        el.textContent = value.toLocaleString();
        if (progress < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
}

function updateLobFilter(lobs) {
    const select = document.getElementById('filter-lob');
    const currentValue = select.value;

    // Only update if options changed
    const existingOptions = Array.from(select.options).slice(1).map(o => o.value);
    if (JSON.stringify(existingOptions) === JSON.stringify(lobs)) return;

    // Clear existing (keep first "All" option)
    while (select.options.length > 1) select.remove(1);

    lobs.sort().forEach(lob => {
        const option = document.createElement('option');
        option.value = lob;
        option.textContent = lob;
        select.add(option);
    });

    select.value = currentValue;
}

// ── Load Tickets ─────────────────────────────────────────────────────────────
async function loadTickets() {
    const lobFilter = document.getElementById('filter-lob').value;
    const statusFilter = document.getElementById('filter-status').value;

    let endpoint = '/api/tickets?limit=50';
    if (lobFilter) endpoint += `&lob=${encodeURIComponent(lobFilter)}`;
    if (statusFilter) endpoint += `&status=${encodeURIComponent(statusFilter)}`;

    const tickets = await apiFetch(endpoint);
    if (!tickets) return;

    const tbody = document.getElementById('tickets-tbody');

    if (!tickets.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <div class="empty-state-text">No tickets found. Click <strong>Run Now</strong> to process Change Requests.</div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = tickets.map(t => `
        <tr>
            <td>
                <button class="cr-link" onclick="openTicketModal('${escapeHtml(t.cr_number)}')" title="Click to drill down into details">
                    ${escapeHtml(t.cr_number)} ↗
                </button>
            </td>
            <td>${escapeHtml(truncate(t.short_description, 50))}</td>
            <td>${escapeHtml(t.lob_impacted || '—')}</td>
            <td>${escapeHtml(t.mail_codes || '—')}</td>
            <td>${escapeHtml(t.qa_lead || '—')}</td>
            <td><span class="status-pill ${t.status}">${formatStatus(t.status)}</span></td>
            <td>${formatTimestamp(t.processed_at)}</td>
        </tr>
    `).join('');
}

// ── Load Runs ────────────────────────────────────────────────────────────────
async function loadRuns() {
    const runs = await apiFetch('/api/pipeline/runs?limit=10');
    if (!runs) return;

    const container = document.getElementById('runs-list');

    if (!runs.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-text">No pipeline runs yet.</div>
            </div>
        `;
        return;
    }

    // Update header status badge
    const latestRun = runs[0];
    updatePipelineStatus(latestRun);

    container.innerHTML = runs.map(r => `
        <div class="run-item">
            <span class="run-id">#${r.id}</span>
            <span class="status-pill ${r.status}">${formatStatus(r.status)}</span>
            <div class="run-meta">
                <span>📡 ${r.trigger}</span>
                <span>📋 ${r.tickets_found} found</span>
                <span>✅ ${r.tickets_notified} notified</span>
                <span>🕐 ${formatTimestamp(r.started_at)}</span>
            </div>
        </div>
    `).join('');
}

function updatePipelineStatus(run) {
    const badge = document.getElementById('pipeline-status');
    badge.className = `status-badge ${run.status}`;

    const statusText = {
        running: 'Running',
        completed: 'Idle',
        failed: 'Failed',
    };

    badge.textContent = statusText[run.status] || run.status;

    // Disable/enable Run button
    const btn = document.getElementById('btn-run');
    if (run.status === 'running') {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Running...';
    } else {
        btn.disabled = false;
        btn.innerHTML = '▶ Run Now';
    }
}

// ── Load Schedule ────────────────────────────────────────────────────────────
async function loadSchedule() {
    const schedule = await apiFetch('/api/schedule');
    if (!schedule) return;

    const badge = document.getElementById('schedule-info');

    if (schedule.active) {
        const mins = Math.round(schedule.interval_seconds / 60);
        badge.className = 'status-badge idle';
        badge.textContent = `⏱ Every ${mins}m`;
        if (schedule.next_run_at) {
            badge.title = `Next run: ${new Date(schedule.next_run_at).toLocaleTimeString()}`;
        }
    } else {
        badge.className = 'status-badge';
        badge.style.background = 'rgba(255,255,255,0.03)';
        badge.style.color = 'var(--text-muted)';
        badge.style.border = '1px solid var(--border-subtle)';
        badge.textContent = '⏱ Scheduler Off';
    }
}

// ── Trigger Pipeline ─────────────────────────────────────────────────────────
async function triggerPipeline() {
    const btn = document.getElementById('btn-run');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Starting...';

    const result = await apiPost('/api/pipeline/run');

    if (result) {
        if (result.error_message === 'Pipeline is already running') {
            showToast('Pipeline is already running.', 'info');
        } else {
            showToast(`Pipeline run #${result.id} started!`, 'success');
        }
    } else {
        showToast('Failed to trigger pipeline.', 'error');
        btn.disabled = false;
        btn.innerHTML = '▶ Run Now';
    }

    // Refresh after a short delay
    setTimeout(refreshAll, 1000);
}

// ── LOB Chart ────────────────────────────────────────────────────────────────
function renderLobChart(lobBreakdown) {
    const container = document.getElementById('lob-chart');
    const entries = Object.entries(lobBreakdown);

    if (!entries.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-text">No LOB data yet.</div>
            </div>
        `;
        return;
    }

    const maxVal = Math.max(...entries.map(([, v]) => v));

    container.innerHTML = `
        <div class="lob-bar-container">
            ${entries.sort((a, b) => b[1] - a[1]).map(([lob, count]) => {
                const pct = Math.max((count / maxVal) * 100, 8);
                return `
                    <div class="lob-bar">
                        <span class="lob-bar-label">${escapeHtml(lob)}</span>
                        <div class="lob-bar-track">
                            <div class="lob-bar-fill" style="width: ${pct}%">${count}</div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// ── Toast Notifications ──────────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');

    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;

    container.appendChild(toast);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// ── Utility Functions ────────────────────────────────────────────────────────
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, maxLen) {
    if (!str) return '';
    return str.length > maxLen ? str.substring(0, maxLen) + '…' : str;
}

function formatStatus(status) {
    const labels = {
        processing: '🔄 Processing',
        extracted: '🔮 Extracted',
        extraction_failed: '❌ Extraction Failed',
        mapped: '📍 Mapped',
        mapping_failed: '❌ Mapping Failed',
        notified: '✅ Notified',
        notification_failed: '❌ Notify Failed',
        running: '🔄 Running',
        completed: '✅ Completed',
        failed: '❌ Failed',
        idle: '💤 Idle',
    };
    return labels[status] || status;
}

function formatTimestamp(isoString) {
    if (!isoString) return '—';
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;

        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return isoString;
    }
}

// ── Drill-down Modal ─────────────────────────────────────────────────────────
let currentModalCrNumber = null;

async function openTicketModal(crNumber) {
    currentModalCrNumber = crNumber;
    const modal = document.getElementById('ticket-modal');
    const modalBody = document.getElementById('modal-body');
    const crHeader = document.getElementById('modal-cr-number');
    const statusPill = document.getElementById('modal-status-pill');
    const processedAt = document.getElementById('modal-processed-at');
    const reprocessBtn = document.getElementById('modal-reprocess-btn');

    crHeader.textContent = crNumber;
    statusPill.className = 'status-pill';
    statusPill.textContent = 'Loading...';
    processedAt.textContent = 'Fetching details...';
    modalBody.innerHTML = `
        <div style="padding: 40px; text-align: center; color: var(--text-muted);">
            <div class="spinner" style="margin: 0 auto 12px; width: 24px; height: 24px;"></div>
            Loading Change Request details...
        </div>
    `;

    modal.classList.add('active');

    const ticket = await apiFetch(`/api/tickets/${encodeURIComponent(crNumber)}`);
    if (!ticket) {
        modalBody.innerHTML = `
            <div style="padding: 30px; text-align: center; color: var(--accent-red);">
                Failed to load details for ${escapeHtml(crNumber)}.
            </div>
        `;
        return;
    }

    statusPill.className = `status-pill ${ticket.status}`;
    statusPill.textContent = formatStatus(ticket.status);
    processedAt.textContent = `Processed: ${formatTimestamp(ticket.processed_at)} (${new Date(ticket.processed_at).toLocaleString()})`;

    // Mail codes chips
    const mailCodesList = ticket.mail_codes 
        ? ticket.mail_codes.split(',').map(c => `<span class="mail-code-chip">${escapeHtml(c.trim())}</span>`).join(' ')
        : '<span style="color: var(--text-muted)">None detected</span>';

    // Notifications audit log
    let notifsHtml = '';
    if (ticket.notifications && ticket.notifications.length) {
        notifsHtml = ticket.notifications.map(n => `
            <div class="notif-item">
                <div class="notif-item-left">
                    <div class="notif-item-recipients">📧 ${escapeHtml(n.recipients)}</div>
                    <div class="notif-item-meta">${escapeHtml(n.subject)} • ${formatTimestamp(n.sent_at)}</div>
                </div>
                <div>
                    <span class="status-pill ${n.success ? 'notified' : 'notification_failed'}">
                        ${n.success ? '✅ Sent' : '❌ Failed'}
                    </span>
                </div>
            </div>
        `).join('');
    } else if (ticket.status === 'notified') {
        notifsHtml = `
            <div class="notif-item">
                <div class="notif-item-left">
                    <div class="notif-item-recipients">📧 ${escapeHtml(ticket.qa_lead || 'QA Team')}</div>
                    <div class="notif-item-meta">Dispatched at ${formatTimestamp(ticket.notified_at)}</div>
                </div>
                <span class="status-pill notified">✅ Sent</span>
            </div>
        `;
    } else {
        notifsHtml = '<div style="font-size: 0.85rem; color: var(--text-muted); padding: 8px 0;">No notifications dispatched yet.</div>';
    }

    // Error alert if error_message is set
    const errorBoxHtml = ticket.error_message ? `
        <div style="padding: 12px 16px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: var(--radius-sm); color: #fca5a5; font-size: 0.85rem; display: flex; align-items: flex-start; gap: 8px;">
            <span>⚠️</span>
            <div>
                <strong>Pipeline Error:</strong> ${escapeHtml(ticket.error_message)}
            </div>
        </div>
    ` : '';

    modalBody.innerHTML = `
        ${errorBoxHtml}

        <!-- Section 1: Summary -->
        <div class="modal-section">
            <div class="modal-section-title">📌 Summary &amp; Scope</div>
            <div style="font-size: 1.05rem; font-weight: 600; color: var(--text-bright); margin-bottom: 12px;">
                ${escapeHtml(ticket.short_description)}
            </div>
            <div class="modal-grid-3">
                <div class="modal-field">
                    <span class="modal-field-label">Impacted LOB</span>
                    <span class="modal-field-value" style="color: var(--accent-blue); font-weight: 600;">
                        ${escapeHtml(ticket.lob_impacted || 'Unknown')}
                    </span>
                </div>
                <div class="modal-field">
                    <span class="modal-field-label">Assigned QA Lead</span>
                    <span class="modal-field-value">
                        ${escapeHtml(ticket.qa_lead || 'Unassigned')}
                    </span>
                </div>
                <div class="modal-field">
                    <span class="modal-field-label">Pipeline Run</span>
                    <span class="modal-field-value">
                        #${ticket.pipeline_run_id}
                    </span>
                </div>
            </div>
        </div>

        <!-- Section 2: Extracted Mail Codes -->
        <div class="modal-section">
            <div class="modal-section-title">🏷️ Extracted Mail Codes</div>
            <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
                ${mailCodesList}
            </div>
        </div>

        <!-- Section 3: Notification Audit Log -->
        <div class="modal-section">
            <div class="modal-section-title">📬 Email Notification Audit</div>
            ${notifsHtml}
        </div>

        <!-- Section 4: Full ServiceNow Description -->
        <div class="modal-section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div class="modal-section-title" style="margin-bottom: 0;">📝 Original ServiceNow Description</div>
                <button class="btn btn-outline" style="padding: 4px 10px; font-size: 0.75rem;" onclick="copyDescription()">
                    📋 Copy Text
                </button>
            </div>
            <pre class="description-box" id="modal-raw-description">${escapeHtml(ticket.description)}</pre>
        </div>

        <!-- Section 5: Metadata -->
        <div class="modal-section" style="background: transparent; border-style: dashed;">
            <div class="modal-grid-2" style="font-size: 0.8rem;">
                <div><span style="color: var(--text-muted)">Sys ID:</span> <code>${escapeHtml(ticket.sys_id || 'N/A')}</code></div>
                <div><span style="color: var(--text-muted)">Notified Timestamp:</span> <code>${ticket.notified_at || 'N/A'}</code></div>
            </div>
        </div>
    `;
}

function closeTicketModal() {
    const modal = document.getElementById('ticket-modal');
    modal.classList.remove('active');
    currentModalCrNumber = null;
}

function handleModalBackdropClick(event) {
    if (event.target.id === 'ticket-modal') {
        closeTicketModal();
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeTicketModal();
    }
});

async function reprocessModalTicket() {
    if (!currentModalCrNumber) return;
    const btn = document.getElementById('modal-reprocess-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Re-processing...';

    const result = await apiPost(`/api/tickets/${encodeURIComponent(currentModalCrNumber)}/reprocess`);
    btn.disabled = false;
    btn.innerHTML = '🔄 Re-process';

    if (result) {
        showToast(`CR ${currentModalCrNumber} re-processed!`, 'success');
        await openTicketModal(currentModalCrNumber);
        refreshAll();
    } else {
        showToast(`Failed to re-process ${currentModalCrNumber}`, 'error');
    }
}

function copyDescription() {
    const el = document.getElementById('modal-raw-description');
    if (!el) return;
    navigator.clipboard.writeText(el.textContent).then(() => {
        showToast('Description copied to clipboard!', 'info');
    });
}
