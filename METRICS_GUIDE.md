# 📊 Metrics Collection Guide

This guide explains how to collect and analyze product metrics for your Telegram Transcription Bot.

## 🎯 What Metrics Are Collected

The metrics system automatically tracks:

### 👥 User Metrics
- **Total Users**: Everyone who has ever interacted with your bot
- **Active Users**: Users who used the bot recently (7d/30d)
- **New Users**: Users who started using the bot recently (7d)
- **User Details**: Username, first name, last name, first seen, last seen

### 📁 File Processing Metrics
- **Total Files Processed**: All files ever uploaded
- **Files by Time Period**: Files processed in the last 7 days
- **Success Rate**: Percentage of successful transcriptions
- **Average File Size**: Mean size of uploaded files
- **Average Processing Time**: Mean time to process files
- **Files Per User**: Average number of files per user

### 📊 Daily Statistics
- **Daily Active Users**: Users per day
- **Daily Files Processed**: Files per day
- **Daily Total Size**: Total MB processed per day
- **Success/Failure Counts**: Daily transcription results

### 🔍 Top Users Analysis
- **Most Active Users**: Users with the most files processed
- **Usage Patterns**: Average file sizes per user
- **User Engagement**: When users were first/last seen

## 🛠️ How It Works

### 1. SQLite Database
- **Zero Setup**: No external services required
- **Local Storage**: Database stored in `./temp/metrics.db`
- **Automatic Schema**: Tables created automatically on first run
- **Lightweight**: Minimal impact on bot performance

### 2. Automatic Tracking
The bot automatically tracks:
- User interactions (start, help, file uploads)
- File processing events (start, success, failure)
- Daily statistics updates
- Processing times and error messages

### 3. Data Storage
```
users table:           User information and activity
file_events table:     File processing events
interactions table:    User interactions and commands
daily_stats table:     Pre-computed daily summaries
```

## 📈 Viewing Your Metrics

### Option 1: Command Line Dashboard
```bash
# Run the terminal dashboard
python scripts/metrics_dashboard.py
```

This shows:
- Quick summary with key metrics
- User statistics
- File processing statistics
- Top users by activity
- Daily statistics for the last 7 days

### Option 2: Web Dashboard
```bash
# Install Flask (if not already installed)
pip install flask

# Run the web dashboard
python scripts/web_dashboard.py
```

Then open `http://localhost:5000` in your browser for a beautiful real-time dashboard with:
- Auto-refresh capability
- Interactive charts and tables
- Mobile-responsive design
- API endpoints for custom integrations

## 🔧 Setup Instructions

### 1. The metrics system is already integrated! 
Just run your bot normally and metrics will be collected automatically.

### 2. View Your Metrics
Choose your preferred method:

**Terminal Dashboard:**
```bash
python scripts/metrics_dashboard.py
```

**Web Dashboard:**
```bash
pip install flask
python scripts/web_dashboard.py
```

### 3. No Configuration Required
The metrics system uses the same temp directory as your bot (configured in `.env`).

## 📋 Key Metrics to Track

### 🎯 Product Metrics
1. **User Growth**: Track total users and new users over time
2. **User Engagement**: Monitor active users (7d/30d) and files per user
3. **Product Performance**: Watch success rates and processing times
4. **Usage Patterns**: Analyze file sizes and user behavior

### 🔍 Business Insights
- **Which users are most active?** (Top users analysis)
- **How fast is your bot growing?** (Daily new users)
- **Is your bot reliable?** (Success rate trends)
- **What's the typical usage pattern?** (Files per user, avg file size)

### 📊 Example Metrics Output
```
📋 QUICK SUMMARY
👥 Total Users: 45
📁 Total Files: 123
✅ Success Rate: 94.3%
📊 Avg File Size: 12.4 MB
📈 Files per User: 2.7

👥 USER STATISTICS
📊 Total Users:           45
🔥 Active Users (7d):     12
📈 Active Users (30d):    28
✨ New Users (7d):        5
```

## 🚀 Advanced Usage

### Custom Queries
If you need custom metrics, you can query the SQLite database directly:

```python
from telegram_bot.services.metrics_service import get_metrics_service

metrics_service = get_metrics_service()
# Database is available at: metrics_service.db_path

# Example custom query
import sqlite3
with sqlite3.connect(metrics_service.db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(timestamp) as date, COUNT(*) as files
        FROM file_events 
        WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY date
    """)
    results = cursor.fetchall()
```

### API Integration
The web dashboard provides REST API endpoints:
- `GET /api/user-stats` - User statistics
- `GET /api/file-stats` - File processing statistics  
- `GET /api/top-users` - Top users by activity
- `GET /api/daily-stats` - Daily statistics

### Exporting Data
```python
# Export to CSV
import csv
from telegram_bot.services.metrics_service import get_metrics_service

metrics_service = get_metrics_service()
users = metrics_service.get_top_users(limit=100)

with open('users.csv', 'w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=users[0].keys())
    writer.writeheader()
    writer.writerows(users)
```

## 🎨 Customization

### Adding New Metrics
To track additional metrics, modify `telegram_bot/services/metrics_service.py`:

1. Add new table columns or tables in `_init_db()`
2. Add tracking methods
3. Add query methods for reporting
4. Update the dashboard scripts

### Dashboard Customization
- **Terminal Dashboard**: Edit `scripts/metrics_dashboard.py`
- **Web Dashboard**: Edit `scripts/web_dashboard.py`
- **Styling**: Modify the CSS in the HTML template

## 🔒 Privacy & Security

### Data Protection
- All data is stored locally in SQLite
- No external services involved
- User data is minimal (only what's needed for metrics)

### GDPR Compliance
- Users can be deleted from the database
- Data is only used for internal analytics
- No personally identifiable information is exposed

### Data Retention
Consider implementing data retention policies:
```python
# Example: Delete old data
cursor.execute("DELETE FROM file_events WHERE timestamp < datetime('now', '-6 months')")
```

## 🔧 Troubleshooting

### Common Issues

**1. "No data available"**
- Make sure the bot has been running and processing files
- Check that users have interacted with the bot

**2. "Database locked"**
- The bot might be running while you're viewing metrics
- This is normal - the database handles concurrent access

**3. "Flask not installed"**
- Install Flask: `pip install flask`
- Or use the terminal dashboard instead

**4. "Permission denied"**
- Check file permissions on the temp directory
- Make sure the bot has write access

### Database Location
The metrics database is stored at:
```
./temp/metrics.db
```

You can copy this file to backup your metrics or analyze it with any SQLite tool.

## 🎯 Next Steps

### 1. Monitor Key Metrics
- Set up regular monitoring of your key metrics
- Track trends over time
- Set up alerts for significant changes

### 2. Analyze User Behavior
- Identify your most active users
- Understand usage patterns
- Optimize based on user needs

### 3. Improve Performance
- Monitor success rates and processing times
- Identify bottlenecks
- Optimize based on real usage data

### 4. Scale Your Analytics
- Consider migrating to a more powerful database for large-scale usage
- Implement real-time dashboards
- Add more sophisticated analytics

---

## 📞 Support

If you need help with metrics collection:
1. Check the troubleshooting section above
2. Review the code in `telegram_bot/services/metrics_service.py`
3. Run the dashboard scripts to see example output

The metrics system is designed to be simple and reliable - it should work out of the box with minimal configuration!