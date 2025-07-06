#!/usr/bin/env python3
"""Simple web dashboard for the Telegram transcription bot metrics."""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from flask import Flask, render_template_string, jsonify
except ImportError:
    print("❌ Flask not installed. Install with: pip install flask")
    sys.exit(1)

from telegram_bot.services.metrics_service import get_metrics_service

app = Flask(__name__)

# HTML template for the dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Bot Metrics Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 28px; }
        .header p { margin: 5px 0 0 0; opacity: 0.9; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-card h3 { margin: 0 0 15px 0; color: #333; font-size: 18px; }
        .stat-item { display: flex; justify-content: space-between; margin: 10px 0; padding: 8px 0; border-bottom: 1px solid #eee; }
        .stat-item:last-child { border-bottom: none; }
        .stat-value { font-weight: bold; color: #667eea; }
        .table-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .table-card h3 { margin: 0 0 15px 0; color: #333; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; font-weight: bold; }
        .refresh-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
        .refresh-btn:hover { background: #5a6fd8; }
        .metric-emoji { font-size: 18px; margin-right: 8px; }
        .loading { text-align: center; padding: 20px; color: #666; }
        .auto-refresh { margin-left: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 Telegram Transcription Bot - Metrics Dashboard</h1>
            <p>Real-time analytics for your bot usage</p>
        </div>
        
        <button class="refresh-btn" onclick="refreshData()">🔄 Refresh Data</button>
        <label class="auto-refresh">
            <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> Auto-refresh (30s)
        </label>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>👥 User Statistics</h3>
                <div id="userStats" class="loading">Loading...</div>
            </div>
            
            <div class="stat-card">
                <h3>📁 File Processing</h3>
                <div id="fileStats" class="loading">Loading...</div>
            </div>
        </div>
        
        <div class="table-card">
            <h3>🏆 Top Users</h3>
            <div id="topUsers" class="loading">Loading...</div>
        </div>
        
        <div class="table-card">
            <h3>📅 Daily Statistics (Last 7 Days)</h3>
            <div id="dailyStats" class="loading">Loading...</div>
        </div>
    </div>

    <script>
        let autoRefreshInterval = null;
        
        function refreshData() {
            loadUserStats();
            loadFileStats();
            loadTopUsers();
            loadDailyStats();
        }
        
        function toggleAutoRefresh() {
            const checkbox = document.getElementById('autoRefresh');
            if (checkbox.checked) {
                autoRefreshInterval = setInterval(refreshData, 30000); // 30 seconds
            } else {
                clearInterval(autoRefreshInterval);
            }
        }
        
        function loadUserStats() {
            fetch('/api/user-stats')
                .then(response => response.json())
                .then(data => {
                    const html = `
                        <div class="stat-item">
                            <span><span class="metric-emoji">📊</span>Total Users</span>
                            <span class="stat-value">${data.total_users}</span>
                        </div>
                        <div class="stat-item">
                            <span><span class="metric-emoji">🔥</span>Active Users (7d)</span>
                            <span class="stat-value">${data.active_users_7d}</span>
                        </div>
                        <div class="stat-item">
                            <span><span class="metric-emoji">📈</span>Active Users (30d)</span>
                            <span class="stat-value">${data.active_users_30d}</span>
                        </div>
                        <div class="stat-item">
                            <span><span class="metric-emoji">✨</span>New Users (7d)</span>
                            <span class="stat-value">${data.new_users_7d}</span>
                        </div>
                    `;
                    document.getElementById('userStats').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('userStats').innerHTML = '<p>Error loading data</p>';
                });
        }
        
        function loadFileStats() {
            fetch('/api/file-stats')
                .then(response => response.json())
                .then(data => {
                    const html = `
                        <div class="stat-item">
                            <span><span class="metric-emoji">📊</span>Total Files</span>
                            <span class="stat-value">${data.total_files}</span>
                        </div>
                        <div class="stat-item">
                            <span><span class="metric-emoji">🔥</span>Files (7d)</span>
                            <span class="stat-value">${data.files_7d}</span>
                        </div>
                        <div class="stat-item">
                            <span><span class="metric-emoji">✅</span>Success Rate</span>
                            <span class="stat-value">${data.success_rate}%</span>
                        </div>
                        <div class="stat-item">
                            <span><span class="metric-emoji">📦</span>Avg File Size</span>
                            <span class="stat-value">${data.avg_file_size_mb} MB</span>
                        </div>
                        <div class="stat-item">
                            <span><span class="metric-emoji">⏱️</span>Avg Processing Time</span>
                            <span class="stat-value">${data.avg_processing_time_seconds}s</span>
                        </div>
                    `;
                    document.getElementById('fileStats').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('fileStats').innerHTML = '<p>Error loading data</p>';
                });
        }
        
        function loadTopUsers() {
            fetch('/api/top-users')
                .then(response => response.json())
                .then(data => {
                    if (data.length === 0) {
                        document.getElementById('topUsers').innerHTML = '<p>No user data available</p>';
                        return;
                    }
                    
                    let html = `
                        <table>
                            <tr>
                                <th>#</th>
                                <th>User ID</th>
                                <th>Username</th>
                                <th>Files</th>
                                <th>Avg Size (MB)</th>
                                <th>Last Seen</th>
                            </tr>
                    `;
                    
                    data.forEach((user, index) => {
                        const username = user.username || user.first_name || 'N/A';
                        const lastSeen = user.last_seen ? user.last_seen.substring(0, 19) : 'N/A';
                        html += `
                            <tr>
                                <td>${index + 1}</td>
                                <td>${user.user_id}</td>
                                <td>${username}</td>
                                <td>${user.file_count}</td>
                                <td>${user.avg_file_size_mb}</td>
                                <td>${lastSeen}</td>
                            </tr>
                        `;
                    });
                    
                    html += '</table>';
                    document.getElementById('topUsers').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('topUsers').innerHTML = '<p>Error loading data</p>';
                });
        }
        
        function loadDailyStats() {
            fetch('/api/daily-stats')
                .then(response => response.json())
                .then(data => {
                    if (data.length === 0) {
                        document.getElementById('dailyStats').innerHTML = '<p>No daily statistics available</p>';
                        return;
                    }
                    
                    let html = `
                        <table>
                            <tr>
                                <th>Date</th>
                                <th>Active Users</th>
                                <th>Files Processed</th>
                                <th>Total Size (MB)</th>
                                <th>Successful</th>
                                <th>Failed</th>
                            </tr>
                    `;
                    
                    data.forEach(day => {
                        html += `
                            <tr>
                                <td>${day.date}</td>
                                <td>${day.active_users}</td>
                                <td>${day.files_processed}</td>
                                <td>${day.total_file_size_mb}</td>
                                <td>${day.successful_transcriptions}</td>
                                <td>${day.failed_transcriptions}</td>
                            </tr>
                        `;
                    });
                    
                    html += '</table>';
                    document.getElementById('dailyStats').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('dailyStats').innerHTML = '<p>Error loading data</p>';
                });
        }
        
        // Load data on page load
        window.addEventListener('load', refreshData);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/user-stats')
def api_user_stats():
    """API endpoint for user statistics."""
    try:
        metrics_service = get_metrics_service()
        stats = metrics_service.get_user_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/file-stats')
def api_file_stats():
    """API endpoint for file statistics."""
    try:
        metrics_service = get_metrics_service()
        stats = metrics_service.get_file_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/top-users')
def api_top_users():
    """API endpoint for top users."""
    try:
        metrics_service = get_metrics_service()
        users = metrics_service.get_top_users(limit=10)
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/daily-stats')
def api_daily_stats():
    """API endpoint for daily statistics."""
    try:
        metrics_service = get_metrics_service()
        stats = metrics_service.get_daily_stats(days=7)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🎥 Telegram Transcription Bot - Web Dashboard")
    print("📊 Starting web server...")
    print("🌐 Open http://localhost:5000 in your browser")
    print("🔄 The dashboard will auto-refresh every 30 seconds when enabled")
    print("⚠️  Press Ctrl+C to stop the server")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n✅ Dashboard stopped.")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        print("Make sure port 5000 is available.")