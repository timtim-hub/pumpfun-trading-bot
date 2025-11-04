// Pump.fun Trading Bot - Dashboard JavaScript

// Initialize Socket.IO connection
const socket = io();

// State
let performanceChart = null;
let pnlChart = null;
let capitalHistory = [];
let tradesData = [];

// DOM Elements
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeCharts();
    loadInitialData();
    setupEventListeners();
    loadTradingMode(); // Load and display current trading mode
});

// Socket.IO Event Handlers
socket.on('connect', () => {
    console.log('🔌 Connected to WebSocket server');
    console.log('Socket ID:', socket.id);
    showToast('Connected', 'WebSocket connection established', 'success');
});

socket.on('disconnect', () => {
    console.log('🔌 Disconnected from WebSocket server');
    showToast('Disconnected', 'Lost connection to server', 'error');
    updateStatus(false);
});

socket.on('bot_update', (data) => {
    console.log('📨 ==========================================');
    console.log('📨 BOT UPDATE RECEIVED at', new Date().toLocaleTimeString());
    console.log('📨 Data:', JSON.stringify(data, null, 2));
    console.log('📨 Capital:', data.capital.current, 'SOL');
    console.log('📨 ROI:', data.capital.roi, '%');
    console.log('📨 ==========================================');
    updateDashboard(data);
});

socket.on('bot_started', (data) => {
    showToast('Bot Started', data.message, 'success');
    updateStatus(true);
});

socket.on('bot_stopped', (data) => {
    showToast('Bot Stopped', data.message, 'success');
    updateStatus(false);
});

socket.on('error', (data) => {
    showToast('Error', data.message, 'error');
});

// Event Listeners
function setupEventListeners() {
    startBtn.addEventListener('click', () => {
        console.log('🚀 START BUTTON CLICKED - Emitting start_bot event...');
        socket.emit('start_bot');
        console.log('✅ start_bot event emitted!');
        startBtn.disabled = true;
        startBtn.innerHTML = '<span class="btn-icon">⏳</span> Starting...';
    });

    stopBtn.addEventListener('click', () => {
        socket.emit('stop_bot');
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<span class="btn-icon">⏳</span> Stopping...';
    });

    document.getElementById('resetBtn').addEventListener('click', resetState);
    document.getElementById('refreshTrades').addEventListener('click', loadTrades);
    
    document.getElementById('filterOutcome').addEventListener('change', (e) => {
        filterTrades(e.target.value);
    });

    // Mode toggle switch
    document.getElementById('modeToggle').addEventListener('change', handleModeToggle);

    // Chart period buttons
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            updateChartPeriod(e.target.dataset.period);
        });
    });
}

// Update Dashboard with Bot Data
function updateDashboard(data) {
    console.log('🎨 UPDATING DASHBOARD...');
    console.log('🎨 Current data:', data);
    
    try {
        // Update capital metrics with animation
        const currentCapitalEl = document.getElementById('currentCapital');
        const oldValue = parseFloat(currentCapitalEl.textContent);
        const newValue = data.capital.current;
        
        console.log('🎨 Old capital:', oldValue, '→ New capital:', newValue);
        
        if (oldValue !== newValue) {
            currentCapitalEl.style.animation = 'pulse 0.5s ease-in-out';
            setTimeout(() => currentCapitalEl.style.animation = '', 500);
            console.log('🎨 ✨ Capital changed! Animation triggered');
        }
        
        currentCapitalEl.textContent = `${newValue.toFixed(4)} SOL`;
        document.getElementById('initialCapital').textContent = data.capital.initial.toFixed(4);
        document.getElementById('peakCapital').textContent = data.capital.peak.toFixed(4);
        
        console.log('🎨 ✅ Capital updated in DOM');
    } catch (e) {
        console.error('❌ Error updating capital:', e);
    }
    
    try {
        const roiValue = data.capital.roi;
        const roiElement = document.getElementById('roi');
        roiElement.textContent = `${roiValue >= 0 ? '+' : ''}${roiValue.toFixed(2)}%`;
        roiElement.className = `metric-value ${roiValue >= 0 ? 'positive' : 'negative'}`;
        
        const capitalChange = document.getElementById('capitalChange');
        capitalChange.textContent = `${roiValue >= 0 ? '+' : ''}${roiValue.toFixed(2)}%`;
        capitalChange.className = `change ${roiValue >= 0 ? 'positive' : 'negative'}`;

        // Update P&L (display in SOL with suffix)
        document.getElementById('totalPnl').textContent = `${data.pnl.total.toFixed(4)} SOL`;
        document.getElementById('netPnl').textContent = `${data.pnl.net.toFixed(4)} SOL`;

        // Update trades
        document.getElementById('totalTrades').textContent = data.trades.total;
        document.getElementById('winningTrades').textContent = data.trades.winning;
        document.getElementById('losingTrades').textContent = data.trades.losing;
        
        const winRate = data.trades.win_rate;
        document.getElementById('winRate').textContent = `${winRate}%`;

        // Update activity
        document.getElementById('tokensEvaluated').textContent = data.activity.evaluated;
        document.getElementById('tokensSkipped').textContent = data.activity.skipped;
        document.getElementById('activePositions').textContent = data.activity.active_positions;

        // Update active positions
        if (data.positions && data.positions.length > 0) {
            updatePositions(data.positions);
        } else {
            document.getElementById('positionsCard').style.display = 'none';
        }

        // Update chart
        capitalHistory.push({
            time: new Date(data.timestamp),
            capital: data.capital.current
        });
        
        // Keep last 100 data points
        if (capitalHistory.length > 100) {
            capitalHistory.shift();
        }
        
        updatePerformanceChart();

        // Refresh trades periodically
        if (Math.random() < 0.1) { // 10% chance each update
            loadTrades();
        }
    } catch (e) {
        console.error('❌ Error updating dashboard:', e);
    }
}

// Update Status Indicator
function updateStatus(running) {
    if (running) {
        statusIndicator.classList.add('active');
        statusText.textContent = 'Running';
        startBtn.style.display = 'none';
        stopBtn.style.display = 'inline-flex';
        stopBtn.disabled = false;
    } else {
        statusIndicator.classList.remove('active');
        statusText.textContent = 'Stopped';
        startBtn.style.display = 'inline-flex';
        startBtn.disabled = false;
        startBtn.innerHTML = '<span class="btn-icon">▶</span> Start Bot';
        stopBtn.style.display = 'none';
    }
}

// Update Active Positions
function updatePositions(positions) {
    const positionsCard = document.getElementById('positionsCard');
    const positionsList = document.getElementById('positionsList');
    const positionCount = document.getElementById('positionCount');
    
    positionsCard.style.display = 'block';
    positionCount.textContent = positions.length;
    
    positionsList.innerHTML = positions.map(pos => `
        <div class="position-item">
            <div class="position-info">
                <h4>${pos.symbol}</h4>
                <p>Entry: ${pos.entry_price.toFixed(8)} SOL | Current: ${pos.current_price.toFixed(8)} SOL | Hold: ${pos.hold_time}s</p>
            </div>
            <div class="position-pnl">
                <div class="pnl-value ${pos.pnl_sol >= 0 ? 'positive' : 'negative'}">
                    ${pos.pnl_sol >= 0 ? '+' : ''}${pos.pnl_sol.toFixed(4)} SOL
                </div>
                <div class="pnl-percent ${pos.pnl_percent >= 0 ? 'positive' : 'negative'}">
                    ${pos.pnl_percent >= 0 ? '+' : ''}${pos.pnl_percent.toFixed(2)}%
                </div>
            </div>
        </div>
    `).join('');
}

// Initialize Charts
function initializeCharts() {
    // Performance Chart
    const perfCtx = document.getElementById('performanceChart').getContext('2d');
    performanceChart = new Chart(perfCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Capital (SOL)',
                data: [],
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(26, 31, 58, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#8b92b2',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b92b2',
                        maxTicksLimit: 8
                    }
                },
                y: {
                    display: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b92b2',
                        callback: function(value) {
                            return value.toFixed(4) + ' SOL';
                        }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });

    // P&L Distribution Chart
    const pnlCtx = document.getElementById('pnlChart').getContext('2d');
    pnlChart = new Chart(pnlCtx, {
        type: 'doughnut',
        data: {
            labels: ['Wins', 'Losses', 'Breakeven'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(239, 68, 68, 0.8)',
                    'rgba(139, 146, 178, 0.8)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#8b92b2',
                        padding: 16,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(26, 31, 58, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#8b92b2',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12
                }
            },
            cutout: '70%'
        }
    });
}

// Update Performance Chart
function updatePerformanceChart() {
    if (!performanceChart || capitalHistory.length === 0) return;
    
    const labels = capitalHistory.map(d => {
        const time = d.time;
        return `${time.getHours()}:${String(time.getMinutes()).padStart(2, '0')}:${String(time.getSeconds()).padStart(2, '0')}`;
    });
    
    const data = capitalHistory.map(d => d.capital);
    
    performanceChart.data.labels = labels;
    performanceChart.data.datasets[0].data = data;
    performanceChart.update('none');
}

// Update P&L Chart
function updatePnlChart(wins, losses, breakeven) {
    if (!pnlChart) return;
    
    pnlChart.data.datasets[0].data = [wins, losses, breakeven];
    pnlChart.update();
}

// Load Initial Data
// Reset State
async function resetState() {
    if (!confirm('⚠️ Reset Bot State?\n\nThis will:\n• Reset capital to initial 2 SOL\n• Clear all trade history\n• Reset all metrics\n\nYou need to RESTART the bot after resetting.\n\nContinue?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/reset_state', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showToast('Success', 'State reset! Please stop and restart the bot.', 'success');
            // Suggest stopping the bot
            if (statusIndicator.classList.contains('active')) {
                socket.emit('stop_bot');
            }
        } else {
            showToast('Error', data.error || 'Failed to reset state', 'error');
        }
    } catch (error) {
        console.error('Error resetting state:', error);
        showToast('Error', 'Failed to reset state: ' + error.message, 'error');
    }
}

async function loadInitialData() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        console.log('📂 Loading initial data:', data);
        
        // Update dashboard with saved state (even if bot not running)
        if (data.capital) {
            console.log('💰 Restoring saved capital:', data.capital.current, 'SOL');
            
            // Update capital display
            document.getElementById('currentCapital').textContent = `${data.capital.current.toFixed(4)} SOL`;
            document.getElementById('initialCapital').textContent = data.capital.initial.toFixed(4);
            document.getElementById('peakCapital').textContent = data.capital.peak.toFixed(4);
            
            // Update ROI
            const roiValue = data.capital.roi;
            const roiElement = document.getElementById('roi');
            roiElement.textContent = `${roiValue >= 0 ? '+' : ''}${roiValue.toFixed(2)}%`;
            roiElement.className = `metric-value ${roiValue >= 0 ? 'positive' : 'negative'}`;
            
            const capitalChange = document.getElementById('capitalChange');
            capitalChange.textContent = `${roiValue >= 0 ? '+' : ''}${roiValue.toFixed(2)}%`;
            capitalChange.className = `change ${roiValue >= 0 ? 'positive' : 'negative'}`;
            
            // Update trades
            if (data.trades) {
                document.getElementById('totalTrades').textContent = data.trades.total;
                document.getElementById('winningTrades').textContent = data.trades.winning;
                document.getElementById('losingTrades').textContent = data.trades.losing;
                document.getElementById('winRate').textContent = `${data.trades.win_rate}%`;
            }
            
            // Update P&L
            if (data.pnl) {
                document.getElementById('totalPnl').textContent = data.pnl.total;
                document.getElementById('netPnl').textContent = data.pnl.net;
            }
        }
        
        if (data.running) {
            updateStatus(true);
        }
        
        await loadTrades();
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

// Load Trades
async function loadTrades() {
    try {
        const response = await fetch('/api/trades');
        tradesData = await response.json();
        
        // Update P&L chart
        const wins = tradesData.filter(t => t.outcome === 'profit').length;
        const losses = tradesData.filter(t => t.outcome === 'loss').length;
        const breakeven = tradesData.filter(t => t.outcome === 'breakeven').length;
        updatePnlChart(wins, losses, breakeven);
        
        // Display trades
        displayTrades(tradesData);
    } catch (error) {
        console.error('Error loading trades:', error);
    }
}

// Display Trades
function displayTrades(trades) {
    const tbody = document.getElementById('tradesTableBody');
    
    if (trades.length === 0) {
        tbody.innerHTML = '<tr class="empty-state"><td colspan="9">No trades yet. Start the bot to begin trading!</td></tr>';
        return;
    }
    
    tbody.innerHTML = trades.reverse().map(trade => {
        const pnlClass = trade.pnl_sol >= 0 ? 'positive' : 'negative';
        const outcomeClass = trade.outcome === 'profit' ? 'outcome-profit' : 'outcome-loss';
        const time = new Date(trade.timestamp).toLocaleTimeString();
        
        return `
            <tr>
                <td>${time}</td>
                <td><strong>${trade.symbol}</strong></td>
                <td>${trade.entry_price.toFixed(8)}</td>
                <td>${trade.exit_price.toFixed(8)}</td>
                <td class="${pnlClass}">${trade.pnl_sol >= 0 ? '+' : ''}${trade.pnl_sol.toFixed(4)}</td>
                <td class="${pnlClass}">${trade.pnl_percent >= 0 ? '+' : ''}${trade.pnl_percent.toFixed(2)}%</td>
                <td>${trade.hold_time.toFixed(0)}s</td>
                <td>${trade.exit_reason}</td>
                <td><span class="outcome-badge ${outcomeClass}">${trade.outcome}</span></td>
            </tr>
        `;
    }).join('');
}

// Filter Trades
function filterTrades(filter) {
    if (filter === 'all') {
        displayTrades(tradesData);
    } else {
        const filtered = tradesData.filter(t => t.outcome === filter);
        displayTrades(filtered);
    }
}

// Update Chart Period
function updateChartPeriod(period) {
    // Filter capital history based on period
    let filtered = [...capitalHistory];
    
    if (period === '10m') {
        const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000);
        filtered = capitalHistory.filter(d => d.time >= tenMinutesAgo);
    } else if (period === '1h') {
        const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
        filtered = capitalHistory.filter(d => d.time >= oneHourAgo);
    }
    
    const labels = filtered.map(d => {
        const time = d.time;
        return `${time.getHours()}:${String(time.getMinutes()).padStart(2, '0')}:${String(time.getSeconds()).padStart(2, '0')}`;
    });
    
    const data = filtered.map(d => d.capital);
    
    performanceChart.data.labels = labels;
    performanceChart.data.datasets[0].data = data;
    performanceChart.update();
}

// Toast Notifications
function showToast(title, message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    
    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-content">
            <h4>${title}</h4>
            <p>${message}</p>
        </div>
    `;
    
    document.getElementById('toastContainer').appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Utility Functions
function formatNumber(num, decimals = 2) {
    return num.toFixed(decimals);
}

function formatPercent(num) {
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
}

function formatSOL(num) {
    return `${num.toFixed(4)} SOL`;
}

// Load Trading Mode
async function loadTradingMode() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        const mode = config.mode || 'dry_run';
        
        // Update toggle switch
        const modeToggle = document.getElementById('modeToggle');
        modeToggle.checked = (mode === 'live');
        
        // Update mode labels
        updateModeLabels(mode);
        
        console.log(`📊 Trading Mode Loaded: ${mode === 'live' ? 'LIVE' : 'DRY RUN'}`);
    } catch (error) {
        console.error('Error loading trading mode:', error);
    }
}

// Update mode labels styling
function updateModeLabels(mode) {
    const dryLabel = document.getElementById('modeLabel');
    const liveLabel = document.getElementById('modeLabelLive');
    
    if (mode === 'live') {
        dryLabel.style.color = '#8b92b2';
        dryLabel.style.fontWeight = '500';
        liveLabel.style.color = '#ef4444';
        liveLabel.style.fontWeight = '600';
    } else {
        dryLabel.style.color = '#6366f1';
        dryLabel.style.fontWeight = '600';
        liveLabel.style.color = '#8b92b2';
        liveLabel.style.fontWeight = '500';
    }
}

// Handle mode toggle
async function handleModeToggle(event) {
    const isLive = event.target.checked;
    const newMode = isLive ? 'live' : 'dry_run';
    
    // Check if bot is running
    if (statusIndicator.classList.contains('active')) {
        showToast('Error', 'Please stop the bot before changing mode', 'error');
        // Revert toggle
        event.target.checked = !isLive;
        return;
    }
    
    // Confirm if switching to live
    if (isLive) {
        const confirmed = confirm(
            '⚠️ WARNING: Switching to LIVE TRADING MODE\n\n' +
            'The bot will trade with REAL MONEY from your wallet.\n\n' +
            'Make sure your wallet is set up and funded.\n\n' +
            'Do you want to continue?'
        );
        
        if (!confirmed) {
            event.target.checked = false;
            return;
        }
    }
    
    // Show loading
    showToast('Info', `Switching to ${isLive ? 'Live Trading' : 'Dry Run'} mode...`, 'info');
    
    try {
        // Save mode to config
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: newMode })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            updateModeLabels(newMode);
            showToast(
                'Success', 
                `Switched to ${isLive ? '💰 Live Trading' : '🧪 Dry Run'} mode. Refreshing data...`, 
                'success'
            );
            
            // Refresh dashboard data
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            throw new Error(data.error || 'Failed to switch mode');
        }
    } catch (error) {
        console.error('Error switching mode:', error);
        showToast('Error', 'Failed to switch mode: ' + error.message, 'error');
        // Revert toggle
        event.target.checked = !isLive;
    }
}

// Auto-refresh trades every 10 seconds
setInterval(() => {
    if (statusIndicator.classList.contains('active')) {
        loadTrades();
    }
}, 10000);

