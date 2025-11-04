// Settings Page JavaScript

let currentWalletAddress = '';
let currentBalance = 0;

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

    // Wallet actions
    document.getElementById('importPhantomBtn').addEventListener('click', importPhantomWallet);
    document.getElementById('createWalletBtn').addEventListener('click', createWallet);
    document.getElementById('checkBalanceBtn').addEventListener('click', checkBalance);
    document.getElementById('loadWalletBtn')?.addEventListener('click', loadWallet);

    // Settings actions
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
    document.getElementById('resetSettingsBtn').addEventListener('click', resetSettings);
}

// Handle mode change
function handleModeChange(e) {
    const mode = e.target.value;
    const walletCard = document.getElementById('walletCard');
    const modeBadge = document.getElementById('currentModeBadge');
    
    if (mode === 'live') {
        walletCard.style.display = 'block';
        modeBadge.textContent = 'LIVE';
        modeBadge.className = 'badge badge-danger';
    } else {
        walletCard.style.display = 'none';
        modeBadge.textContent = 'DRY RUN';
        modeBadge.className = 'badge';
    }
}

// Import Phantom wallet
async function importPhantomWallet() {
    const privateKey = document.getElementById('phantomPrivateKey').value.trim();
    
    if (!privateKey) {
        showToast('Error', 'Please paste your Phantom private key', 'error');
        return;
    }
    
    const btn = document.getElementById('importPhantomBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Importing...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/wallet/import', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                private_key: privateKey,
                wallet_path: 'wallet.json'
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Clear the private key input for security
            document.getElementById('phantomPrivateKey').value = '';
            document.getElementById('phantomPrivateKey').type = 'password';
            
            // Show success
            currentWalletAddress = data.address;
            
            // Update UI
            document.getElementById('walletCreatedInfo').style.display = 'block';
            document.getElementById('createdWalletPath').textContent = data.path;
            document.getElementById('walletAddressDisplay').value = data.address;
            document.getElementById('step1Status').textContent = '✅ Completed';
            document.getElementById('step1Status').className = 'step-status completed';
            
            // Update wallet path input
            document.getElementById('walletPath').value = data.path;
            
            showToast('Success', 'Phantom wallet imported! Your wallet is ready to use.', 'success');
            
            // Auto-check balance
            setTimeout(() => {
                document.getElementById('step2').scrollIntoView({ behavior: 'smooth', block: 'center' });
                // Auto check balance after a moment
                setTimeout(() => checkBalance(), 1000);
            }, 500);
            
        } else {
            showToast('Error', data.error || 'Failed to import wallet', 'error');
        }
    } catch (error) {
        console.error('Error importing wallet:', error);
        showToast('Error', 'Failed to import wallet: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Create new wallet
async function createWallet() {
    const btn = document.getElementById('createWalletBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Creating...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/wallet/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                wallet_path: 'wallet.json'
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Show success
            currentWalletAddress = data.address;
            
            // Update UI
            document.getElementById('walletCreatedInfo').style.display = 'block';
            document.getElementById('createdWalletPath').textContent = data.path;
            document.getElementById('walletAddressDisplay').value = data.address;
            document.getElementById('step1Status').textContent = '✅ Completed';
            document.getElementById('step1Status').className = 'step-status completed';
            
            // Update wallet path input
            document.getElementById('walletPath').value = data.path;
            
            showToast('Success', 'Wallet created successfully! Now fund it with SOL.', 'success');
            
            // Highlight step 2
            document.getElementById('step2').scrollIntoView({ behavior: 'smooth', block: 'center' });
            
        } else {
            showToast('Error', data.error || 'Failed to create wallet', 'error');
        }
    } catch (error) {
        console.error('Error creating wallet:', error);
        showToast('Error', 'Failed to create wallet: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Load existing wallet
async function loadWallet() {
    const walletPath = document.getElementById('walletPath').value;
    const btn = document.getElementById('loadWalletBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Loading...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/wallet/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ wallet_path: walletPath })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            currentWalletAddress = data.address;
            currentBalance = data.balance;
            
            // Update Step 1
            document.getElementById('walletCreatedInfo').style.display = 'block';
            document.getElementById('createdWalletPath').textContent = walletPath;
            document.getElementById('walletAddressDisplay').value = data.address;
            document.getElementById('step1Status').textContent = '✅ Completed';
            document.getElementById('step1Status').className = 'step-status completed';
            
            showToast('Success', 'Wallet loaded successfully!', 'success');
            
            // Auto-check balance
            setTimeout(() => checkBalance(), 500);
            
        } else {
            showToast('Error', data.error || 'Failed to load wallet', 'error');
        }
    } catch (error) {
        console.error('Error loading wallet:', error);
        showToast('Error', 'Failed to load wallet: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Check wallet balance
async function checkBalance() {
    const walletPath = document.getElementById('walletPath').value;
    const btn = document.getElementById('checkBalanceBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Checking...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/wallet/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ wallet_path: walletPath })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            currentBalance = data.balance;
            
            // Show balance info
            document.getElementById('balanceInfo').style.display = 'block';
            document.getElementById('currentBalance').textContent = `${data.balance.toFixed(4)} SOL`;
            
            // Calculate USD value (approximate SOL price: $100)
            const solPrice = 100; // This could be fetched from an API
            const usdValue = data.balance * solPrice;
            document.getElementById('usdValue').textContent = `$${usdValue.toFixed(2)}`;
            
            // Update status
            const balanceStatus = document.getElementById('balanceStatus');
            if (data.balance >= 0.1) {
                balanceStatus.textContent = '✅ Ready to Trade';
                balanceStatus.className = 'badge badge-success';
                document.getElementById('step3Status').textContent = '✅ Completed';
                document.getElementById('step3Status').className = 'step-status completed';
                showToast('Success', `Wallet funded with ${data.balance.toFixed(4)} SOL!`, 'success');
            } else if (data.balance > 0) {
                balanceStatus.textContent = '⚠️ Low Balance';
                balanceStatus.className = 'badge badge-warning';
                showToast('Warning', 'Balance is low. Consider adding more SOL.', 'warning');
            } else {
                balanceStatus.textContent = '❌ No Balance';
                balanceStatus.className = 'badge badge-danger';
                showToast('Info', 'Wallet has no balance. Please send SOL to start trading.', 'info');
            }
            
            // Update wallet status in header
            document.getElementById('walletStatus').textContent = `${data.balance.toFixed(4)} SOL`;
            document.getElementById('walletStatus').className = 'badge badge-success';
            
        } else {
            showToast('Error', data.error || 'Failed to check balance', 'error');
            document.getElementById('balanceStatus').textContent = '❌ Error';
            document.getElementById('balanceStatus').className = 'badge badge-danger';
        }
    } catch (error) {
        console.error('Error checking balance:', error);
        showToast('Error', 'Failed to check balance: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Copy wallet address
function copyAddress() {
    const addressInput = document.getElementById('walletAddressDisplay');
    addressInput.select();
    document.execCommand('copy');
    showToast('Copied', 'Wallet address copied to clipboard!', 'success');
}

// Load current configuration
async function loadCurrentConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        // Populate form fields
        document.getElementById('maxPositionSize').value = config.risk?.max_position_size_percent || 25;
        document.getElementById('maxConcurrent').value = config.risk?.max_concurrent_trades || 1;
        document.getElementById('profitTarget').value = config.exit?.profit_target_percent || 50;
        document.getElementById('stopLoss').value = config.exit?.stop_loss_percent || 10;
        document.getElementById('trailingStop').value = config.exit?.trailing_stop_percent || 10;
        document.getElementById('maxHoldTime').value = config.exit?.max_hold_time_seconds || 90;
        
        document.getElementById('minVolume').value = config.entry?.min_early_volume_sol || 0.5;
        document.getElementById('evalWindow').value = config.entry?.evaluation_window_seconds || 3;
        document.getElementById('minCurve').value = config.entry?.min_bonding_curve_percent || 2;
        document.getElementById('maxCurve').value = config.entry?.max_bonding_curve_percent || 60;
        
        document.getElementById('maxDailyLoss').value = config.risk?.max_daily_loss_percent || 20;
        document.getElementById('maxLossPerTrade').value = config.risk?.max_loss_per_trade_sol || 0.1;
        document.getElementById('minBalance').value = config.risk?.min_sol_balance || 0.05;

        // Set mode
        const mode = config.mode || 'dry_run';
        document.getElementById(mode === 'dry_run' ? 'dryRunRadio' : 'liveRadio').checked = true;
        handleModeChange({ target: { value: mode } });

        // Wallet path
        document.getElementById('walletPath').value = config.wallet?.keypair_path || 'wallet.json';

    } catch (error) {
        console.error('Error loading config:', error);
        showToast('Error', 'Failed to load configuration', 'error');
    }
}

// Save settings
async function saveSettings() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    
    // Validate wallet setup for live mode
    if (mode === 'live') {
        if (!currentWalletAddress) {
            showToast('Error', 'Please create or load a wallet first!', 'error');
            document.getElementById('step1').scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
        
        if (currentBalance < 0.05) {
            const confirmed = confirm(
                `⚠️ Warning: Your wallet balance is very low (${currentBalance.toFixed(4)} SOL).\n\n` +
                `You need at least 0.05 SOL for trading and fees. \n\n` +
                `Do you want to save anyway?`
            );
            if (!confirmed) return;
        }
    }

    const config = {
        mode: mode,
        wallet: {
            keypair_path: document.getElementById('walletPath').value
        },
        risk: {
            max_position_size_percent: parseInt(document.getElementById('maxPositionSize').value),
            max_concurrent_trades: parseInt(document.getElementById('maxConcurrent').value),
            max_daily_loss_percent: parseInt(document.getElementById('maxDailyLoss').value),
            max_loss_per_trade_sol: parseFloat(document.getElementById('maxLossPerTrade').value),
            min_sol_balance: parseFloat(document.getElementById('minBalance').value)
        },
        entry: {
            min_early_volume_sol: parseFloat(document.getElementById('minVolume').value),
            evaluation_window_seconds: parseInt(document.getElementById('evalWindow').value),
            min_bonding_curve_percent: parseInt(document.getElementById('minCurve').value),
            max_bonding_curve_percent: parseInt(document.getElementById('maxCurve').value)
        },
        exit: {
            profit_target_percent: parseInt(document.getElementById('profitTarget').value),
            stop_loss_percent: parseInt(document.getElementById('stopLoss').value),
            trailing_stop_percent: parseInt(document.getElementById('trailingStop').value),
            max_hold_time_seconds: parseInt(document.getElementById('maxHoldTime').value)
        }
    };

    const btn = document.getElementById('saveSettingsBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Saving...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('Success', 'Settings saved successfully! Restart the bot to apply changes.', 'success');
            
            if (mode === 'live') {
                showToast('Info', '⚠️ LIVE MODE ENABLED - Bot will trade with real money!', 'warning');
            }
        } else {
            showToast('Error', data.error || 'Failed to save settings', 'error');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showToast('Error', 'Failed to save settings: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Reset settings
function resetSettings() {
    if (confirm('Are you sure you want to reset all settings to defaults?')) {
        // Reset to defaults
        document.getElementById('maxPositionSize').value = 25;
        document.getElementById('maxConcurrent').value = 1;
        document.getElementById('profitTarget').value = 50;
        document.getElementById('stopLoss').value = 10;
        document.getElementById('trailingStop').value = 10;
        document.getElementById('maxHoldTime').value = 90;
        
        document.getElementById('minVolume').value = 0.5;
        document.getElementById('evalWindow').value = 3;
        document.getElementById('minCurve').value = 2;
        document.getElementById('maxCurve').value = 60;
        
        document.getElementById('maxDailyLoss').value = 20;
        document.getElementById('maxLossPerTrade').value = 0.1;
        document.getElementById('minBalance').value = 0.05;
        
        document.getElementById('dryRunRadio').checked = true;
        handleModeChange({ target: { value: 'dry_run' } });
        
        showToast('Success', 'Settings reset to defaults', 'success');
    }
}

// Toast notification function
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    toast.innerHTML = `
        <div class="toast-icon">${icons[type] || 'ℹ️'}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}
