/* ============================================================================
   Global Variables & Configuration
   ============================================================================ */

const API_BASE_URL = 'http://localhost:8000';  // Backend API on port 8000
const REFRESH_INTERVAL = 2000;  // 2 seconds

let refreshInterval = null;

/* ============================================================================
   Initialization
   ============================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Check service status
    checkServiceStatus();
    
    // Setup event listeners
    setupEventListeners();
    
    // Load initial data
    loadBackupsList();
    loadRestoreBackups();  // Load backups for restoration tab
    loadJobsList();
    
    // Setup auto-refresh
    setupAutoRefresh();
}

/* ============================================================================
   Event Listeners Setup
   ============================================================================ */

function setupEventListeners() {
    // Tab navigation
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', (e) => switchTab(e.target.dataset.tab));
    });

    // Backup form
    document.getElementById('backupForm').addEventListener('submit', handleBackupSubmit);

    // Load workspaces button
    document.getElementById('loadWorkspacesBtn').addEventListener('click', loadWorkspacesFromAPI);
    
    // Workspace selection
    document.getElementById('workspaceSelect').addEventListener('change', handleWorkspaceSelection);

    // Refresh buttons
    document.getElementById('refreshHistoryBtn').addEventListener('click', loadBackupsList);
    document.getElementById('refreshJobsBtn').addEventListener('click', loadJobsList);

    // ===== New Restoration Workflow Events =====
    
    // Backup selection
    document.getElementById('restoreBackupSelect').addEventListener('change', handleBackupSelection);
    
    // Show backup details
    document.getElementById('showBackupDetailsBtn').addEventListener('click', showBackupDetails);
    
    // Plan restoration
    document.getElementById('planRestorationBtn').addEventListener('click', planRestoration);
    
    // Execute restoration
    document.getElementById('executeRestorationBtn').addEventListener('click', executeRestoration);
}

/* ============================================================================
   Service Status
   ============================================================================ */

async function checkServiceStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/status`);
        if (response.ok) {
            const data = await response.json();
            updateStatusIndicator(true);
            loadBackupsList();  // Load available backups for restore
        } else {
            updateStatusIndicator(false);
        }
    } catch (error) {
        console.error('Error checking service status:', error);
        updateStatusIndicator(false);
    }
}

function updateStatusIndicator(isHealthy) {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    
    if (isHealthy) {
        statusDot.classList.remove('inactive');
        statusText.textContent = 'Service Online';
    } else {
        statusDot.classList.add('inactive');
        statusText.textContent = 'Service Offline';
    }
}

/* ============================================================================
   Tab Navigation
   ============================================================================ */

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Deactivate all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Activate button
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Load data if needed
    if (tabName === 'history') {
        loadBackupsList();
    } else if (tabName === 'jobs') {
        loadJobsList();
    }
}

/* ============================================================================
   Workspace Management
   ============================================================================ */

async function loadWorkspacesFromAPI() {
    try {
        const btn = document.getElementById('loadWorkspacesBtn');
        const spinner = document.getElementById('loadingSpinner');
        
        btn.disabled = true;
        spinner.style.display = 'inline';
        
        const response = await fetch(`${API_BASE_URL}/api/workspaces`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success' && data.workspaces) {
            populateWorkspaceDropdown(data.workspaces);
            showNotification(`Loaded ${data.count} workspaces`, 'success');
        } else {
            throw new Error('Invalid response format');
        }
    } catch (error) {
        console.error('Error loading workspaces:', error);
        showNotification('Error loading workspaces: ' + error.message, 'error');
    } finally {
        document.getElementById('loadWorkspacesBtn').disabled = false;
        document.getElementById('loadingSpinner').style.display = 'none';
    }
}

function populateWorkspaceDropdown(workspaces) {
    const select = document.getElementById('workspaceSelect');
    
    // Clear existing options (except the first one)
    while (select.options.length > 1) {
        select.remove(1);
    }
    
    // Add workspace options
    workspaces.forEach(ws => {
        const option = document.createElement('option');
        option.value = ws.id;
        option.textContent = `${ws.name} (${ws.type})${ws.is_premium_capacity ? ' [Premium]' : ''}`;
        select.appendChild(option);
    });
}

async function handleWorkspaceSelection(e) {
    const workspaceId = e.target.value;
    
    if (!workspaceId) {
        document.getElementById('workspaceInfo').style.display = 'none';
        return;
    }
    
    try {
        // Set the selected workspace ID in the manual input
        document.getElementById('workspaceId').value = workspaceId;
        
        // Fetch detailed workspace info
        const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Display workspace info
            document.getElementById('infoName').textContent = data.workspace.name;
            document.getElementById('infoReports').textContent = data.reports_count;
            document.getElementById('infoDatasets').textContent = data.datasets_count;
            document.getElementById('infoDashboards').textContent = data.dashboards_count;
            document.getElementById('workspaceInfo').style.display = 'block';
        }
    } catch (error) {
        console.error('Error fetching workspace details:', error);
        showNotification('Error loading workspace details: ' + error.message, 'error');
    }
}

/* ============================================================================
   Backup Functionality
   ============================================================================ */

async function handleBackupSubmit(e) {
    e.preventDefault();

    const workspaceId = document.getElementById('workspaceId').value.trim();

    if (!workspaceId) {
        showNotification('Please enter a workspace ID', 'error');
        return;
    }

    try {
        showLoadingModal(true);

        const response = await fetch(`${API_BASE_URL}/api/backup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ workspace_id: workspaceId })
        });

        const data = await response.json();

        if (response.ok) {
            // Reset form
            document.getElementById('backupForm').reset();

            // Show success
            document.getElementById('backupError').style.display = 'none';
            document.getElementById('resultBackupId').textContent = data.backup_id;
            document.getElementById('resultStatus').textContent = data.success ? 'In Progress' : 'Failed';
            document.getElementById('resultTimestamp').textContent = new Date(data.timestamp).toLocaleString();
            document.getElementById('backupResult').style.display = 'block';

            showNotification('Backup started successfully!', 'success');

            // Reload jobs list
            setTimeout(loadJobsList, 1000);
        } else {
            showError(data.detail || 'Failed to start backup', 'backupError');
        }
    } catch (error) {
        console.error('Error starting backup:', error);
        showError('Error: ' + error.message, 'backupError');
    } finally {
        showLoadingModal(false);
    }
}

/* ============================================================================
   Restore Functionality
   ============================================================================ */

async function handleRestoreSubmit(e) {
    e.preventDefault();

    const workspaceId = document.getElementById('restoreWorkspaceId').value.trim();
    const backupFile = document.getElementById('backupFile').value || undefined;

    if (!workspaceId) {
        showNotification('Please enter a target workspace ID', 'error');
        return;
    }

    try {
        showLoadingModal(true);

        const payload = { workspace_id: workspaceId };
        if (backupFile) {
            payload.backup_file = backupFile;
        }

        const response = await fetch(`${API_BASE_URL}/api/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            // Reset form
            document.getElementById('restoreForm').reset();

            // Show success
            document.getElementById('restoreError').style.display = 'none';
            document.getElementById('resultRestoreId').textContent = data.restore_id || 'N/A';
            document.getElementById('restoreResultStatus').textContent = 'In Progress';
            document.getElementById('restoreResultTimestamp').textContent = new Date(data.timestamp).toLocaleString();
            document.getElementById('restoreResult').style.display = 'block';

            showNotification('Restore started successfully!', 'success');

            // Reload jobs list
            setTimeout(loadJobsList, 1000);
        } else {
            showError(data.detail || 'Failed to start restore', 'restoreError');
        }
    } catch (error) {
        console.error('Error starting restore:', error);
        showError('Error: ' + error.message, 'restoreError');
    } finally {
        showLoadingModal(false);
    }
}

/* ============================================================================
   Load Backups List
   ============================================================================ */

async function loadBackupsList() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/backups`);
        const data = await response.json();

        const container = document.getElementById('historyContainer');
        const selectElement = document.getElementById('backupFile');

        if (data.backups && data.backups.length > 0) {
            // Update history view
            if (container) {
                container.innerHTML = data.backups.map(backupId => `
                    <div class="list-item">
                        <div class="list-item-content">
                            <h3>Backup ${backupId.substring(0, 8)}</h3>
                            <p><strong>ID:</strong> ${backupId}</p>
                            <p>Click download to export</p>
                        </div>
                        <div class="list-item-actions">
                            <button class="btn btn-secondary" onclick="downloadBackup('${backupId}')">
                                📥 Download
                            </button>
                            <button class="btn btn-secondary" onclick="viewBackupDetails('${backupId}')">
                                👁️ View
                            </button>
                        </div>
                    </div>
                `).join('');
            }

            // Update restore dropdown if it exists
            if (selectElement) {
                selectElement.innerHTML = '<option value="">-- Use Latest Backup --</option>' + 
                    data.backups.map(id => `<option value="${id}">${id.substring(0, 8)}</option>`).join('');
            }
        } else {
            if (container) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>📭 No backups available yet</p>
                        <p>Create a backup from the "Backup" tab</p>
                    </div>
                `;
            }
            if (selectElement) {
                selectElement.innerHTML = '<option value="">-- No Backups Available --</option>';
            }
        }
    } catch (error) {
        console.error('Error loading backups:', error);
        const historyContainer = document.getElementById('historyContainer');
        if (historyContainer) {
            historyContainer.innerHTML = `
                <div class="alert alert-error">
                    <p>Error loading backups: ${error.message}</p>
                </div>
            `;
        }
    }
}

/* ============================================================================
   Load Jobs List
   ============================================================================ */

async function loadJobsList() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/jobs`);
        const data = await response.json();

        const container = document.getElementById('jobsContainer');

        if (data.jobs && Object.keys(data.jobs).length > 0) {
            const jobsList = Object.entries(data.jobs).map(([jobId, jobInfo]) => {
                const statusClass = jobInfo.status.toLowerCase();
                const statusEmoji = {
                    'in_progress': '⏳',
                    'completed': '✅',
                    'failed': '❌'
                }[jobInfo.status] || '❓';

                return `
                    <div class="list-item">
                        <div class="list-item-content">
                            <h3>Job ${jobId.substring(0, 8)}</h3>
                            <p><strong>Type:</strong> ${jobInfo.workspace_id ? 'Workspace: ' + jobInfo.workspace_id : 'Unknown'}</p>
                            <p><strong>Status:</strong> <span class="status-badge ${statusClass}">${statusEmoji} ${jobInfo.status}</span></p>
                            <p><strong>Started:</strong> ${formatDate(jobInfo.timestamp)}</p>
                            ${jobInfo.error ? `<p><strong>Error:</strong> ${jobInfo.error}</p>` : ''}
                            ${jobInfo.restored_items ? `
                                <p><strong>Restored:</strong> 
                                ${Object.entries(jobInfo.restored_items).map(([k, v]) => `${k}: ${v}`).join(', ')}
                                </p>
                            ` : ''}
                        </div>
                        <div class="list-item-actions">
                            <button class="btn btn-secondary" onclick="loadJobsList()">🔄 Refresh</button>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = jobsList.join('');
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <p>📭 No active jobs</p>
                    <p>Start a backup or restore to see jobs here</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading jobs:', error);
        document.getElementById('jobsContainer').innerHTML = `
            <div class="alert alert-error">
                <p>Error loading jobs: ${error.message}</p>
            </div>
        `;
    }
}

/* ============================================================================
   Backup Actions
   ============================================================================ */

async function downloadBackup(backupId) {
    try {
        window.location.href = `${API_BASE_URL}/api/backup/${backupId}/download`;
        showNotification('Backup download started', 'success');
    } catch (error) {
        console.error('Error downloading backup:', error);
        showNotification('Error downloading backup', 'error');
    }
}

async function viewBackupDetails(backupId) {
    try {
        showLoadingModal(true);

        const response = await fetch(`${API_BASE_URL}/api/backup/${backupId}/download`);
        const backupData = await response.json();

        const detailsHtml = `
            <div class="alert alert-info">
                <h3>Backup Details</h3>
                <div style="text-align: left; overflow-x: auto;">
                    <p><strong>Backup ID:</strong> ${backupId}</p>
                    <p><strong>Workspace ID:</strong> ${backupData.workspace_id}</p>
                    <p><strong>Timestamp:</strong> ${formatDate(backupData.timestamp)}</p>
                    <hr style="margin: 15px 0;">
                    <p><strong>Reports:</strong> ${backupData.reports.length}</p>
                    <p><strong>Datasets:</strong> ${backupData.datasets.length}</p>
                    <p><strong>Dataflows:</strong> ${backupData.dataflows.length}</p>
                    <p><strong>Dashboards:</strong> ${backupData.dashboards.length}</p>
                    <p><strong>Apps:</strong> ${backupData.apps.length}</p>
                    <p><strong>Refresh Schedules:</strong> ${backupData.refresh_schedules.length}</p>
                </div>
            </div>
        `;

        // Show in a modal or alert
        alert(`Backup Details:\n\nID: ${backupId}\nWorkspace: ${backupData.workspace_id}\nReports: ${backupData.reports.length}\nDatasets: ${backupData.datasets.length}\nDataflows: ${backupData.dataflows.length}\nDashboards: ${backupData.dashboards.length}\nApps: ${backupData.apps.length}\nSchedules: ${backupData.refresh_schedules.length}`);
    } catch (error) {
        console.error('Error viewing backup:', error);
        showNotification('Error loading backup details', 'error');
    } finally {
        showLoadingModal(false);
    }
}

/* ============================================================================
   UI Helpers
   ============================================================================ */

function showLoadingModal(show) {
    const modal = document.getElementById('loadingModal');
    modal.style.display = show ? 'flex' : 'none';
}

function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    const notificationText = document.getElementById('notificationText');

    notificationText.textContent = message;
    notification.className = `toast ${type}`;
    notification.style.display = 'block';

    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

function showError(message, elementId) {
    const element = document.getElementById(elementId);
    const messageElement = element.querySelector('p');
    messageElement.textContent = message;
    element.style.display = 'block';
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        return new Date(dateString).toLocaleString();
    } catch {
        return dateString;
    }
}

/* ============================================================================
   Auto-Refresh
   ============================================================================ */

function setupAutoRefresh() {
    // Check if any jobs are in progress and refresh accordingly
    refreshInterval = setInterval(() => {
        const jobsTab = document.getElementById('jobs-tab');
        if (jobsTab.classList.contains('active') || document.hidden) {
            return;  // Only refresh when tab is visible or not focused
        }
    }, REFRESH_INTERVAL);
}

// Auto-refresh jobs when tab becomes visible
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        loadJobsList();
        checkServiceStatus();
    }
});

/* ============================================================================
   NEW RESTORATION WORKFLOW
   ============================================================================ */

/**
 * Populate available backups in restore tab - show backups with reports
 */
async function loadRestoreBackups() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/backups`);
        const data = await response.json();
        
        const select = document.getElementById('restoreBackupSelect');
        select.innerHTML = '';
        
        if (data.count > 0) {
            // Filter backups to only show those with reports and meaningful IDs
            let backupsWithReports = [];
            
            for (const backup of data.backups) {
                try {
                    // Skip UUID-format backups (old format)
                    const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(backup);
                    if (isUUID) {
                        console.log(`Skipping old UUID-format backup: ${backup}`);
                        continue;
                    }
                    
                    // Try to get PBIX files info (new backup format)
                    const pbixResponse = await fetch(`${API_BASE_URL}/api/backup/${backup}/pbix-files`);
                    
                    if (pbixResponse.ok) {
                        const pbixData = await pbixResponse.json();
                        
                        // Check for exported PBIX files
                        if (pbixData.pbix_files && pbixData.pbix_files.length > 0) {
                            const successfulPbix = pbixData.pbix_files.filter(f => f.export_status === 'success').length;
                            if (successfulPbix > 0) {
                                backupsWithReports.push({
                                    id: backup,
                                    reportCount: successfulPbix,
                                    timestamp: pbixData.metadata?.backup_timestamp || new Date().toISOString(),
                                    type: 'pbix'
                                });
                            }
                        }
                    }
                } catch (err) {
                    console.warn(`Could not check backup ${backup}:`, err);
                }
            }
            
            if (backupsWithReports.length > 0) {
                // Sort by timestamp (newest first)
                backupsWithReports.sort((a, b) => {
                    try {
                        return new Date(b.timestamp) - new Date(a.timestamp);
                    } catch {
                        return 0;
                    }
                });
                
                backupsWithReports.forEach(backup => {
                    const option = document.createElement('option');
                    option.value = backup.id;
                    
                    // Parse backup ID to extract workspace name and timestamp
                    // Format: workspace_name_YYYYMMDD_HHMMSS
                    let displayName = backup.id;
                    let displayDate = '';
                    
                    try {
                        const parts = backup.id.split('_');
                        if (parts.length >= 3) {
                            // Last two parts are date and time
                            const timeStr = parts.pop();  // HHMMSS
                            const dateStr = parts.pop();  // YYYYMMDD
                            const workspaceName = parts.join('_'); // Everything else
                            
                            // Format: YYYYMMDD_HHMMSS -> YYYY-MM-DD HH:MM:SS
                            const year = dateStr.substring(0, 4);
                            const month = dateStr.substring(4, 6);
                            const day = dateStr.substring(6, 8);
                            const hour = timeStr.substring(0, 2);
                            const min = timeStr.substring(2, 4);
                            const sec = timeStr.substring(4, 6);
                            
                            displayName = workspaceName.replace(/_/g, ' ');
                            displayDate = `${year}-${month}-${day} ${hour}:${min}:${sec}`;
                        }
                    } catch (err) {
                        console.warn('Could not parse backup ID:', err);
                        displayDate = new Date(backup.timestamp).toLocaleString();
                    }
                    
                    const typeIcon = backup.type === 'pbix' ? '📄' : '📊';
                    option.textContent = `${typeIcon} ${displayName} | ${backup.reportCount} reports | ${displayDate}`;
                    select.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = '-- No backups with reports available --';
                select.appendChild(option);
            }
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '-- No backups available --';
            select.appendChild(option);
        }
    } catch (error) {
        console.error('Error loading backups:', error);
        showNotification('Error loading backups: ' + error.message, 'error');
        
        const select = document.getElementById('restoreBackupSelect');
        select.innerHTML = '';
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '-- Error loading backups --';
        select.appendChild(option);
    }
}

/**
 * Handle backup selection
 */
function handleBackupSelection(e) {
    const backupId = e.target.value;
    const btn = document.getElementById('showBackupDetailsBtn');
    
    if (backupId) {
        btn.style.display = 'inline-flex';
    } else {
        btn.style.display = 'none';
        document.getElementById('backupDetailsContainer').style.display = 'none';
    }
}

/**
 * Show backup details including PBIX files
 */
async function showBackupDetails() {
    const backupId = document.getElementById('restoreBackupSelect').value;
    
    if (!backupId) {
        showNotification('Please select a backup first', 'error');
        return;
    }
    
    try {
        showLoadingModal(true);
        
        const response = await fetch(`${API_BASE_URL}/api/backup/${backupId}/pbix-files`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        let html = '';
        
        // Export summary
        const summary = data.export_summary || {};
        html += `
            <div class="export-summary">
                <div class="summary-box">
                    <small>Total PBIX Files</small>
                    <strong>${summary.total || 0}</strong>
                </div>
                <div class="summary-box">
                    <small>Successfully Exported</small>
                    <strong>${summary.successful || 0}</strong>
                </div>
                <div class="summary-box">
                    <small>Failed</small>
                    <strong>${summary.failed || 0}</strong>
                </div>
            </div>
        `;
        
        // PBIX files list
        if (data.pbix_files && data.pbix_files.length > 0) {
            html += '<h4 style="margin-top: 20px; color: #d4a574;">📄 Exported PBIX Files</h4>';
            html += '<div class="pbix-files-list">';
            
            data.pbix_files.forEach(file => {
                if (file.export_status === 'success') {
                    html += `
                        <div class="pbix-file-card">
                            <h5>${file.name}</h5>
                            <div class="pbix-file-info">
                                <p><strong>File Size:</strong> ${file.file_size_mb} MB</p>
                                <p><strong>Report ID:</strong> ${file.id.substring(0, 8)}...</p>
                            </div>
                            <span class="pbix-status success">✓ Exported</span>
                        </div>
                    `;
                }
            });
            
            html += '</div>';
        }
        
        document.getElementById('backupDetailsContent').innerHTML = html;
        document.getElementById('backupDetailsContainer').style.display = 'block';
        
        showNotification('Backup details loaded successfully', 'success');
        
    } catch (error) {
        console.error('Error loading backup details:', error);
        showNotification('Error loading backup details: ' + error.message, 'error');
    } finally {
        showLoadingModal(false);
    }
}

/**
 * Plan restoration from backup
 */
async function planRestoration() {
    const backupId = document.getElementById('restoreBackupSelect').value;
    const targetWs = document.getElementById('planTargetWorkspace').value.trim();
    
    if (!backupId || !targetWs) {
        showNotification('Please select a backup and enter target workspace ID', 'error');
        return;
    }
    
    try {
        showLoadingModal(true);
        
        const response = await fetch(`${API_BASE_URL}/api/restore/plan?backup_id=${backupId}&target_workspace_id=${targetWs}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const plan = data.restoration_plan;
        
        let html = '';
        
        // Restoration summary
        const summary = plan.restoration_summary || {};
        html += `
            <div class="export-summary">
                <div class="summary-box">
                    <small>Total Items</small>
                    <strong>${summary.total_items || 0}</strong>
                </div>
                <div class="summary-box">
                    <small>Auto-Restorable</small>
                    <strong>${summary.automatically_restorable || 0}</strong>
                </div>
                <div class="summary-box">
                    <small>Manual Steps</small>
                    <strong>${summary.manual_steps_required || 0}</strong>
                </div>
            </div>
        `;
        
        // Automatic restoration items
        const autoItems = plan.automatic_restoration?.can_restore || [];
        if (autoItems.length > 0) {
            html += '<h4 style="margin-top: 20px; color: #27ae60;">✓ Automatic Restoration</h4>';
            autoItems.forEach(item => {
                html += `
                    <div class="restoration-step">
                        <h4>✓ ${item.type.replace(/_/g, ' ')}</h4>
                        <p>${item.description}</p>
                        ${item.count ? `<p><strong>Count:</strong> ${item.count}</p>` : ''}
                    </div>
                `;
            });
        }
        
        // Manual restoration items
        const manualItems = plan.automatic_restoration?.manual_restoration_required || [];
        if (manualItems.length > 0) {
            html += '<h4 style="margin-top: 20px; color: #f39c12;">⚠ Manual Restoration Required</h4>';
            manualItems.forEach(item => {
                html += `
                    <div class="restoration-step manual">
                        <h4>⚠ ${item.type.replace(/_/g, ' ')}</h4>
                        <p>${item.description}</p>
                        ${item.count ? `<p><strong>Count:</strong> ${item.count}</p>` : ''}
                        ${item.instructions ? `
                            <ul>
                                ${item.instructions.map(instr => `<li>${instr}</li>`).join('')}
                            </ul>
                        ` : ''}
                    </div>
                `;
            });
        }
        
        document.getElementById('restorationPlanContent').innerHTML = html;
        document.getElementById('restorationPlanContainer').style.display = 'block';
        
        // Set target workspace in execute section
        document.getElementById('execTargetWorkspace').value = targetWs;
        
        showNotification('Restoration plan created successfully', 'success');
        
    } catch (error) {
        console.error('Error planning restoration:', error);
        showNotification('Error planning restoration: ' + error.message, 'error');
    } finally {
        showLoadingModal(false);
    }
}

/**
 * Execute restoration using the unified endpoint
 */
async function executeRestoration() {
    const backupId = document.getElementById('restoreBackupSelect').value;
    const targetWs = document.getElementById('execTargetWorkspace').value.trim();
    
    // Get selected components
    const restoreReports = document.getElementById('restoreReportsOption').checked;
    const restoreDatasets = document.getElementById('restoreDatasetsOption').checked;
    const restoreRefreshSchedules = document.getElementById('restoreRefreshSchedulesOption').checked;
    const restoreDashboards = document.getElementById('restoreDashboardsOption').checked;
    const restoreDataflows = document.getElementById('restoreDataflowsOption').checked;
    const restoreApps = document.getElementById('restoreAppsOption').checked;
    
    if (!backupId || !targetWs) {
        showNotification('Please select a backup and enter target workspace ID', 'error');
        return;
    }
    
    if (!restoreReports && !restoreDatasets && !restoreRefreshSchedules && 
        !restoreDashboards && !restoreDataflows && !restoreApps) {
        showNotification('Please select at least one component to restore', 'error');
        return;
    }
    
    try {
        showLoadingModal(true);
        
        // Build query parameters for selected components
        const params = new URLSearchParams({
            backup_id: backupId,
            restore_reports: restoreReports,
            restore_datasets: restoreDatasets,
            restore_refresh_schedules: restoreRefreshSchedules,
            restore_dashboards: restoreDashboards,
            restore_dataflows: restoreDataflows,
            restore_apps: restoreApps
        });
        
        console.log('🔄 Calling unified restoration endpoint');
        console.log(`   Components: Reports=${restoreReports}, Datasets=${restoreDatasets}, Schedules=${restoreRefreshSchedules}, Dashboards=${restoreDashboards}, Dataflows=${restoreDataflows}, Apps=${restoreApps}`);
        
        const response = await fetch(
            `${API_BASE_URL}/api/restore/components/${targetWs}?${params.toString()}`,
            {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            }
        );
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to start restoration');
        }
        
        // Extract selected components for display
        const selectedComponents = [];
        if (restoreReports) selectedComponents.push('Reports (PBIX)');
        if (restoreDatasets) selectedComponents.push('Datasets');
        if (restoreRefreshSchedules) selectedComponents.push('Refresh Schedules');
        if (restoreDashboards) selectedComponents.push('Dashboards');
        if (restoreDataflows) selectedComponents.push('Dataflows');
        if (restoreApps) selectedComponents.push('Apps');
        
        // Display results
        let resultHtml = `
            <p><strong>✅ Unified Restoration Started!</strong></p>
            <p><strong>Job ID:</strong> ${data.job_id}</p>
            <p><strong>Target Workspace:</strong> ${targetWs}</p>
            <p><strong>Backup ID:</strong> ${backupId}</p>
            <hr style="margin: 15px 0;">
            <p><strong>📦 Selected Components (${selectedComponents.length}):</strong></p>
            <ul>
                ${selectedComponents.map(c => `<li>✓ ${c}</li>`).join('')}
            </ul>
            <p style="margin-top: 15px; color: #666;"><em>The restoration is running in the background. Monitor progress in the "Jobs" tab.</em></p>
        `;
        
        document.getElementById('restorationResultContent').innerHTML = resultHtml;
        document.getElementById('restorationError').style.display = 'none';
        document.getElementById('restorationResult').style.display = 'block';
        
        showNotification(`Restoration started: ${selectedComponents.length} components selected`, 'success');
        
        // Reload jobs list after a short delay
        setTimeout(loadJobsList, 1000);
        
    } catch (error) {
        console.error('Error executing restoration:', error);
        document.getElementById('restorationErrorMessage').textContent = error.message;
        document.getElementById('restorationResult').style.display = 'none';
        document.getElementById('restorationError').style.display = 'block';
        showNotification('Error executing restoration: ' + error.message, 'error');
    } finally {
        showLoadingModal(false);
    }
}
