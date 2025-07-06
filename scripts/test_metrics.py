#!/usr/bin/env python3
"""Test script to demonstrate the metrics system with sample data."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from random import randint, choice, uniform

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram_bot.services.metrics_service import get_metrics_service


async def create_sample_data():
    """Create sample data to demonstrate the metrics system."""
    print("🔄 Creating sample metrics data...")
    
    metrics_service = get_metrics_service()
    
    # Sample user data
    sample_users = [
        (12345, "alice_dev", "Alice", "Smith"),
        (67890, "bob_user", "Bob", "Jones"),
        (11111, "charlie_test", "Charlie", "Brown"),
        (22222, "diana_admin", "Diana", "Wilson"),
        (33333, None, "Eve", "Davis"),
        (44444, "frank_power", "Frank", None),
        (55555, "grace_user", "Grace", "Miller"),
        (66666, "henry_dev", "Henry", "Garcia"),
        (77777, "iris_test", "Iris", "Rodriguez"),
        (88888, "jack_admin", "Jack", "Martinez"),
    ]
    
    # Sample file extensions and sizes
    file_extensions = ['.mp4', '.mp3', '.wav', '.avi', '.mov', '.m4a', '.flac', '.ogg']
    file_names = [
        "meeting_recording.mp4",
        "interview_audio.mp3",
        "lecture_video.mp4",
        "podcast_episode.mp3",
        "presentation.mp4",
        "voice_memo.wav",
        "music_demo.m4a",
        "conference_call.mp3",
        "training_video.avi",
        "webinar_recording.mp4"
    ]
    
    # Create users and interactions
    for user_id, username, first_name, last_name in sample_users:
        await metrics_service.track_user(user_id, username, first_name, last_name)
        
        # Track start command
        await metrics_service.track_interaction(user_id, "start", "Bot started")
        
        # Some users use help
        if randint(1, 3) == 1:
            await metrics_service.track_interaction(user_id, "help", "Help requested")
        
        # Generate file processing events
        num_files = randint(1, 8)  # Each user processes 1-8 files
        
        for _ in range(num_files):
            file_name = choice(file_names)
            file_extension = choice(file_extensions)
            file_size_mb = uniform(1.0, 100.0)  # 1MB to 100MB
            
            # Track file upload
            await metrics_service.track_interaction(
                user_id, 
                "file_upload", 
                f"Uploaded: {file_name} ({file_size_mb:.1f}MB)"
            )
            
            # Track file processing
            event_id = await metrics_service.track_file_processing_start(
                user_id, file_name, file_size_mb, file_extension
            )
            
            # Most files succeed (90% success rate)
            processing_time = uniform(10.0, 300.0)  # 10s to 5min
            
            if randint(1, 10) <= 9:  # 90% success rate
                await metrics_service.track_file_processing_complete(event_id, processing_time)
            else:
                error_messages = [
                    "Audio quality too low",
                    "File format not supported",
                    "Processing timeout",
                    "Network error",
                    "Insufficient storage"
                ]
                await metrics_service.track_file_processing_failed(event_id, choice(error_messages))
    
    # Update daily stats
    await metrics_service.update_daily_stats()
    
    print("✅ Sample data created successfully!")


async def main():
    """Main function to create sample data and show results."""
    print("🎥 Telegram Transcription Bot - Metrics Test")
    print("=" * 60)
    
    try:
        # Create sample data
        await create_sample_data()
        
        # Show results
        print("\n📊 SAMPLE METRICS RESULTS:")
        print("=" * 60)
        
        metrics_service = get_metrics_service()
        
        # User stats
        user_stats = metrics_service.get_user_stats()
        print(f"\n👥 USER STATISTICS:")
        print(f"📊 Total Users: {user_stats.get('total_users', 0)}")
        print(f"🔥 Active Users (7d): {user_stats.get('active_users_7d', 0)}")
        print(f"📈 Active Users (30d): {user_stats.get('active_users_30d', 0)}")
        print(f"✨ New Users (7d): {user_stats.get('new_users_7d', 0)}")
        
        # File stats
        file_stats = metrics_service.get_file_stats()
        print(f"\n📁 FILE STATISTICS:")
        print(f"📊 Total Files: {file_stats.get('total_files', 0)}")
        print(f"🔥 Files (7d): {file_stats.get('files_7d', 0)}")
        print(f"✅ Success Rate: {file_stats.get('success_rate', 0):.1f}%")
        print(f"📦 Avg File Size: {file_stats.get('avg_file_size_mb', 0):.1f} MB")
        print(f"⏱️ Avg Processing Time: {file_stats.get('avg_processing_time_seconds', 0):.1f}s")
        
        # Top users
        top_users = metrics_service.get_top_users(limit=5)
        print(f"\n🏆 TOP 5 USERS:")
        for i, user in enumerate(top_users, 1):
            username = user.get('username') or user.get('first_name') or 'N/A'
            print(f"{i}. {username} - {user['file_count']} files")
        
        # Files per user
        if user_stats.get('total_users', 0) > 0:
            files_per_user = file_stats.get('total_files', 0) / user_stats.get('total_users', 1)
            print(f"\n📈 FILES PER USER: {files_per_user:.1f}")
        
        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        print(f"📊 Database location: {metrics_service.db_path}")
        print("\n🎯 NEXT STEPS:")
        print("1. Run: python scripts/metrics_dashboard.py")
        print("2. Or run: python scripts/web_dashboard.py")
        print("3. View your metrics in action!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())