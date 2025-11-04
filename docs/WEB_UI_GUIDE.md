# Web Dashboard Guide

Beautiful real-time web interface for the Pump.fun Trading Bot.

## Overview

The web dashboard provides a stunning, modern interface to monitor and control your trading bot in real-time.

## Features

### 🎨 Modern Dark Theme
- Sleek, professional design
- Smooth animations and transitions
- Responsive layout (desktop & mobile)
- High contrast for readability

### 📊 Real-Time Monitoring
- Live capital tracking
- ROI calculations
- Win rate statistics
- Active positions display
- Performance charts
- P&L distribution

### 🎮 Bot Control
- Start/Stop bot from UI
- Real-time status indicator
- Toast notifications for events
- Error handling and feedback

### 📈 Interactive Charts
- **Performance Chart**: Track capital over time with zoom controls
- **P&L Distribution**: Visualize wins vs. losses
- Chart.js powered visualizations
- Smooth animations

### 📜 Trade History
- Complete trade log
- Filter by outcome (profit/loss)
- Sortable columns
- Real-time updates
- Exit reason tracking

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Web Server
```bash
python web_app.py
```

### 3. Open Dashboard
Navigate to **http://localhost:5001** in your browser

### 4. Start Trading
Click the "▶ Start Bot" button to begin automated trading

## Dashboard Sections

### Header
- **Logo**: Animated rocket icon
- **Status Indicator**: Shows if bot is running (green pulse when active)
- **Start/Stop Buttons**: Control the trading bot

### Metrics Cards
Four key metric cards display:

1. **💰 Capital**
   - Current balance
   - Initial capital
   - Peak capital
   - ROI percentage

2. **📈 ROI**
   - Return on investment percentage
   - Total P&L in SOL
   - Net P&L (after fees)

3. **📊 Trades**
   - Total trades executed
   - Winning trades
   - Losing trades
   - Win rate percentage

4. **🎯 Activity**
   - Tokens evaluated
   - Tokens skipped
   - Active positions

### Performance Chart
Real-time line chart showing capital over time:
- **All**: Show complete history
- **1H**: Last hour
- **10M**: Last 10 minutes
- Hover for detailed tooltips

### P&L Distribution
Doughnut chart showing:
- Winning trades (green)
- Losing trades (red)
- Breakeven trades (gray)

### Active Positions (when trading)
Live display of open positions:
- Token symbol
- Entry price
- Current price
- Unrealized P&L
- Hold time

### Trade History Table
Complete log of all trades:
- Timestamp
- Token symbol
- Entry/Exit prices
- P&L (SOL and %)
- Hold time
- Exit reason
- Outcome badge

**Filter Options:**
- All Trades
- Profits Only
- Losses Only

## Technical Details

### Architecture
```
Frontend (HTML/CSS/JS)
    ↓ WebSocket
Flask Backend
    ↓
Trading Bot Engine
    ↓
Solana Blockchain
```

### Technology Stack
- **Backend**: Flask + Flask-SocketIO
- **Frontend**: Vanilla JavaScript
- **Charts**: Chart.js
- **WebSocket**: Socket.IO
- **Styling**: Custom CSS with animations

### API Endpoints

#### GET /api/status
Get current bot status
```json
{
  "running": true,
  "capital": {"current": 2.5, "roi": 25.0},
  "trades": {"total": 5, "win_rate": 80.0}
}
```

#### GET /api/trades
Get trade history (last 50 trades)
```json
[
  {
    "timestamp": "2025-11-04T15:00:00",
    "symbol": "TOKEN",
    "pnl_sol": 0.15,
    "pnl_percent": 30.5,
    "outcome": "profit"
  }
]
```

#### GET /api/metrics
Get detailed performance metrics

#### GET /api/config
Get current bot configuration

### WebSocket Events

**Client → Server:**
- `start_bot`: Start the trading bot
- `stop_bot`: Stop the trading bot

**Server → Client:**
- `connected`: Connection established
- `bot_update`: Real-time bot status update
- `bot_started`: Bot started successfully
- `bot_stopped`: Bot stopped successfully
- `error`: Error message

## Customization

### Change Port
Edit `web_app.py`:
```python
socketio.run(app, host='0.0.0.0', port=5001)  # Change 5001 to your port
```

### Modify Theme Colors
Edit `static/style.css`:
```css
:root {
    --accent-primary: #6366f1;  /* Change primary color */
    --accent-success: #10b981;  /* Change success color */
    /* ... */
}
```

### Update Refresh Rate
Edit `static/app.js`:
```javascript
// Auto-refresh trades every 10 seconds
setInterval(() => {
    loadTrades();
}, 10000);  // Change interval (milliseconds)
```

## Troubleshooting

### Port Already in Use
If port 5001 is in use:
```bash
# Find process using port
lsof -ti:5001

# Kill the process
kill -9 <PID>

# Or use a different port
python web_app.py --port 5002
```

### WebSocket Not Connecting
- Check firewall settings
- Ensure Flask server is running
- Check browser console for errors
- Try refreshing the page

### No Data Showing
- Start the bot using the "Start Bot" button
- Wait for token detections (30s interval in dry-run mode)
- Check browser console for errors
- Verify API endpoints are responding

### Charts Not Displaying
- Ensure Chart.js CDN is accessible
- Check browser console for JavaScript errors
- Try hard refresh (Ctrl+Shift+R)

## Running in Production

### Use Production Server
For production, use Gunicorn with eventlet:
```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 web_app:app --bind 0.0.0.0:5001
```

### Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://localhost:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### SSL/HTTPS
Use Let's Encrypt for free SSL:
```bash
certbot --nginx -d yourdomain.com
```

## Security

⚠️ **Important Security Notes:**

1. **Never expose to internet without authentication**
2. **Use HTTPS in production**
3. **Implement authentication if needed**
4. **Firewall the port appropriately**
5. **Keep dependencies updated**

## Mobile Access

The dashboard is fully responsive! Access from:
- Desktop browsers (Chrome, Firefox, Safari)
- Mobile browsers (iOS Safari, Chrome Mobile)
- Tablets

Optimal on screens 768px and wider.

## Keyboard Shortcuts

- `Ctrl/Cmd + R`: Refresh page
- `Esc`: Clear any modals (if implemented)

## Tips

1. **Keep browser tab open** for real-time updates
2. **Use multiple monitors** to watch dashboard while doing other work
3. **Filter trades** to analyze performance patterns
4. **Watch the performance chart** to understand capital trends
5. **Monitor active positions** closely during volatile periods

## Future Enhancements

Potential additions:
- [ ] User authentication
- [ ] Historical data export
- [ ] Email/SMS alerts
- [ ] Advanced filtering
- [ ] Custom indicators
- [ ] Trade replay mode
- [ ] Mobile app

## Support

If you encounter issues:
1. Check browser console (F12)
2. Review `web_app.log`
3. Verify Flask server is running
4. Test API endpoints manually
5. Restart the web server

## Screenshots

*(Dashboard is live at http://localhost:5001)*

Features visible:
- Dark theme with gradient background
- Animated metric cards
- Real-time charts
- Trade history table
- Status indicator with pulse animation
- Smooth hover effects

---

**Enjoy your beautiful trading dashboard!** 🚀

