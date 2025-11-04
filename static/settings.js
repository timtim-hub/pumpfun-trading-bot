// Settings Page JavaScript

let currentConfig = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadCurrentConfig();
    setupEventListeners();
});

// Setup Event Listeners
function setupEventListeners() {
    // Mode selection
    document.querySelectorAll('input[name="mode"]').forEach(radio => {
        radio.addEventListener('change', handleModeChange);
    });

    // Wallet check
    document.getElementById('checkWalletBtn').addEventListener('click', checkWallet);

    // Save settings
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);

    // Reset settings
    document.getElementById('resetSettingsBtn').addEventListener('click', resetSettings);
}

// Load Current Configuration
async function loadCurrentConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        currentConfig = config;

        // Populate form fields
        populateForm(config);
    } catch (error) {
        console.error('Error loading config:', error);
        showToast('Error', 'Failed to load configuration', 'error');
    }
}

// Populate Form with Current Config
function populateForm(config) {
    // Mode
    const mode = config.mode || 'dry_run';
    document.querySelector(`input[name="mode"][value="${mode}"]`).checked = true;
    updateModeBadge(mode);
    
    if (mode === 'live') {
        document.getElementById('walletCard').style.display = 'block';
    }

    // Wallet
    if (config.wallet && config.wallet.keypair_path) {
        document.getElementById('walletPath').value = config.wallet.keypair_path;
    }

    // Strategy
    if (config.strategy) {
        document.getElementById('maxPositionSize').value = config.strategy.max_position_size_percent || 25;
        document.getElementById('maxConcurrent').value = config.strategy.max_concurrent_trades || 1;
        document.getElementById('profitTarget').value = config.strategy.profit_target_percent || 50;
        document.getElementById('stopLoss').value = config.strategy.stop_loss_percent || 10;
        document.getElementById('trailingStop').value = config.strategy.trailing_stop_percent || 10;
        document.getElementById('maxHoldTime').value = config.strategy.max_hold_time_seconds || 90;
        document.getElementById('minVolume').value = config.strategy.min_early_volume_sol || 0.5;
        document.getElementById('evalWindow').value = config.strategy.evaluation_window_seconds || 3;
        document.getElementById('minCurve').value = config.strategy.min_bonding_curve_progress || 2;
        document.getElementById('maxCurve').value = config.strategy.max_bonding_curve_progress || 60;
    }

    // Risk
    if (config.risk) {
        document.getElementById('maxDailyLoss').value = config.risk.max_daily_loss_percent || 20;
        document.getElementById('maxLossPerTrade').value = config.risk.max_loss_per_trade_sol || 0.1;
        document.getElementById('minBalance').value = config.risk.min_sol_balance || 0.05;
    }
}

// Handle Mode Change
function handleModeChange(e) {
    const mode = e.target.value;
    updateModeBadge(mode);

    if (mode === 'live') {
        document.getElementById('walletCard').style.display = 'block';
        showToast('Warning', 'Live trading mode selected. Ensure you have a funded wallet!', 'warning');
    } else {
        document.getElementById('walletCard').style.display = 'none';
    }
}

// Update Mode Badge
function updateModeBadge(mode) {
    const badge = document.getElementById('currentModeBadge');
    badge.textContent = mode.toUpperCase();
    badge.className = mode === 'live' ? 'badge badge-warning' : 'badge badge-info';
}

// Check Wallet Balance
async function checkWallet() {
    const walletPath = document.getElementById('walletPath').value;
    const btn = document.getElementById('checkWalletBtn');
    
    btn.disabled = true;
    btn.textContent = 'Checking...';

    try {
        const response = await fetch('/api/wallet/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ keypair_path: walletPath })
        });

        const data = await response.json();

        if (data.error) {
            showToast('Error', data.error, 'error');
            document.getElementById('walletStatus').textContent = 'Not Found';
            document.getElementById('walletStatus').className = 'badge badge-danger';
        } else {
            document.getElementById('walletInfo').style.display = 'block';
            document.getElementById('walletAddress').textContent = data.address;
            document.getElementById('walletBalance').textContent = `${data.balance.toFixed(4)} SOL`;
            document.getElementById('walletStatus').textContent = 'Connected';
            document.getElementById('walletStatus').className = 'badge badge-success';
            
            showToast('Success', `Wallet found with ${data.balance.toFixed(4)} SOL`, 'success');
        }
    } catch (error) {
        console.error('Error checking wallet:', error);
        showToast('Error', 'Failed to check wallet', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Check Balance';
    }
}

// Save Settings
async function saveSettings() {
    const btn = document.getElementById('saveSettingsBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Saving...';

    try {
        const mode = document.querySelector('input[name="mode"]:checked').value;

        // Validate live mode requirements
        if (mode === 'live') {
            const walletPath = document.getElementById('walletPath').value;
            if (!walletPath) {
                showToast('Error', 'Wallet path required for live trading', 'error');
                btn.disabled = false;
                btn.innerHTML = '<span class="btn-icon">💾</span> Save Settings';
                return;
            }

            // Show confirmation for live mode
            if (!confirm('⚠️ WARNING: You are about to enable LIVE TRADING with real money.\n\nRisks:\n- You can lose money\n- Meme tokens are highly volatile\n- No guarantees of profit\n\nAre you sure you want to continue?')) {
                btn.disabled = false;
                btn.innerHTML = '<span class="btn-icon">💾</span> Save Settings';
                return;
            }
        }

        const config = {
            mode: mode,
            strategy: {
                max_position_size_percent: parseFloat(document.getElementById('maxPositionSize').value),
                max_concurrent_trades: parseInt(document.getElementById('maxConcurrent').value),
                profit_target_percent: parseFloat(document.getElementById('profitTarget').value),
                stop_loss_percent: parseFloat(document.getElementById('stopLoss').value),
                trailing_stop_percent: parseFloat(document.getElementById('trailingStop').value),
                max_hold_time_seconds: parseInt(document.getElementById('maxHoldTime').value),
                min_early_volume_sol: parseFloat(document.getElementById('minVolume').value),
                evaluation_window_seconds: parseInt(document.getElementById('evalWindow').value),
                min_bonding_curve_progress: parseFloat(document.getElementById('minCurve').value),
                max_bonding_curve_progress: parseFloat(document.getElementById('maxCurve').value)
            },
            risk: {
                max_daily_loss_percent: parseFloat(document.getElementById('maxDailyLoss').value),
                max_loss_per_trade_sol: parseFloat(document.getElementById('maxLossPerTrade').value),
                min_sol_balance: parseFloat(document.getElementById('minBalance').value)
            },
            wallet: {
                keypair_path: document.getElementById('walletPath').value
            }
        };

        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.error) {
            showToast('Error', data.error, 'error');
        } else {
            showToast('Success', 'Settings saved successfully!', 'success');
            
            if (mode === 'live') {
                showToast('Important', 'Restart the bot for changes to take effect', 'warning');
            }

            // Redirect back to dashboard after short delay
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showToast('Error', 'Failed to save settings', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">💾</span> Save Settings';
    }
}

// Reset Settings
function resetSettings() {
    if (confirm('Reset all settings to defaults?')) {
        loadCurrentConfig();
        showToast('Info', 'Settings reset to defaults', 'info');
    }
}

// Toast Notifications
function showToast(title, message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? '✅' : 
                 type === 'error' ? '❌' : 
                 type === 'warning' ? '⚠️' : 'ℹ️';
    
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

