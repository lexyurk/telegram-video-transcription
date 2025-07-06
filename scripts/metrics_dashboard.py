#!/usr/bin/env python3
"""Simple metrics dashboard for the Telegram transcription bot."""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram_bot.services.metrics_service import get_metrics_service


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_user_stats(metrics_service):
    """Print user statistics."""
    print_header("👥 USER STATISTICS")
    
    stats = metrics_service.get_user_stats()
    
    if not stats:
        print("❌ No user statistics available")
        return
    
    print(f"📊 Total Users:           {stats.get('total_users', 0)}")
    print(f"🔥 Active Users (7d):     {stats.get('active_users_7d', 0)}")
    print(f"📈 Active Users (30d):    {stats.get('active_users_30d', 0)}")
    print(f"✨ New Users (7d):        {stats.get('new_users_7d', 0)}")


def print_file_stats(metrics_service):
    """Print file processing statistics."""
    print_header("📁 FILE PROCESSING STATISTICS")
    
    stats = metrics_service.get_file_stats()
    
    if not stats:
        print("❌ No file statistics available")
        return
    
    print(f"📊 Total Files Processed:     {stats.get('total_files', 0)}")
    print(f"🔥 Files Processed (7d):      {stats.get('files_7d', 0)}")
    print(f"✅ Success Rate:              {stats.get('success_rate', 0):.1f}%")
    print(f"📦 Average File Size:         {stats.get('avg_file_size_mb', 0):.1f} MB")
    print(f"⏱️  Average Processing Time:   {stats.get('avg_processing_time_seconds', 0):.1f} seconds")


def print_top_users(metrics_service):
    """Print top users by file count."""
    print_header("🏆 TOP USERS BY FILE COUNT")
    
    users = metrics_service.get_top_users(limit=10)
    
    if not users:
        print("❌ No user data available")
        return
    
    print(f"{'#':<3} {'User ID':<12} {'Username':<20} {'Files':<6} {'Avg Size':<10} {'Last Seen':<20}")
    print("-" * 80)
    
    for i, user in enumerate(users, 1):
        username = user.get('username') or user.get('first_name') or 'N/A'
        username = username[:18] + '..' if len(username) > 20 else username
        
        print(f"{i:<3} {user['user_id']:<12} {username:<20} {user['file_count']:<6} "
              f"{user['avg_file_size_mb']:<10.1f} {user['last_seen'][:19] if user['last_seen'] else 'N/A':<20}")


def print_daily_stats(metrics_service):
    """Print daily statistics."""
    print_header("📅 DAILY STATISTICS (Last 7 Days)")
    
    stats = metrics_service.get_daily_stats(days=7)
    
    if not stats:
        print("❌ No daily statistics available")
        return
    
    print(f"{'Date':<12} {'Users':<6} {'Files':<6} {'Size (MB)':<10} {'Success':<7} {'Failed':<6}")
    print("-" * 60)
    
    for day in stats:
        print(f"{day['date']:<12} {day['active_users']:<6} {day['files_processed']:<6} "
              f"{day['total_file_size_mb']:<10.1f} {day['successful_transcriptions']:<7} "
              f"{day['failed_transcriptions']:<6}")


def print_summary(metrics_service):
    """Print a quick summary."""
    print_header("📋 QUICK SUMMARY")
    
    user_stats = metrics_service.get_user_stats()
    file_stats = metrics_service.get_file_stats()
    
    print(f"👥 Total Users: {user_stats.get('total_users', 0)}")
    print(f"📁 Total Files: {file_stats.get('total_files', 0)}")
    print(f"✅ Success Rate: {file_stats.get('success_rate', 0):.1f}%")
    print(f"📊 Avg File Size: {file_stats.get('avg_file_size_mb', 0):.1f} MB")
    
    if user_stats.get('total_users', 0) > 0 and file_stats.get('total_files', 0) > 0:
        files_per_user = file_stats.get('total_files', 0) / user_stats.get('total_users', 1)
        print(f"📈 Files per User: {files_per_user:.1f}")


def main():
    """Main dashboard function."""
    print("🎥 Telegram Transcription Bot - Metrics Dashboard")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        metrics_service = get_metrics_service()
        
        # Print all sections
        print_summary(metrics_service)
        print_user_stats(metrics_service)
        print_file_stats(metrics_service)
        print_top_users(metrics_service)
        print_daily_stats(metrics_service)
        
        print(f"\n{'='*60}")
        print("✅ Dashboard generated successfully!")
        print(f"📊 Database location: {metrics_service.db_path}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error generating dashboard: {e}")
        print("Make sure the bot has been running and processing files.")
        sys.exit(1)


if __name__ == "__main__":
    main()