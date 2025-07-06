"""Metrics service for tracking bot usage and performance."""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from telegram_bot.config import get_settings


class MetricsService:
    """Service for tracking and storing bot metrics using SQLite."""
    
    def __init__(self):
        """Initialize the metrics service."""
        self.settings = get_settings()
        self.db_path = Path(self.settings.temp_dir) / "metrics.db"
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # File processing events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size_mb REAL NOT NULL,
                    file_type TEXT NOT NULL,
                    status TEXT NOT NULL,  -- 'started', 'completed', 'failed'
                    processing_time_seconds REAL,
                    error_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Bot commands/interactions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,  -- 'start', 'help', 'file_upload', 'message'
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Daily summaries (for quick reporting)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date DATE PRIMARY KEY,
                    active_users INTEGER DEFAULT 0,
                    files_processed INTEGER DEFAULT 0,
                    total_file_size_mb REAL DEFAULT 0,
                    successful_transcriptions INTEGER DEFAULT 0,
                    failed_transcriptions INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info(f"Metrics database initialized at {self.db_path}")
    
    async def track_user(self, user_id: int, username: Optional[str] = None, 
                        first_name: Optional[str] = None, last_name: Optional[str] = None) -> None:
        """Track a user interaction."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or update user
                cursor.execute("""
                    INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, 
                            COALESCE((SELECT first_seen FROM users WHERE user_id = ?), CURRENT_TIMESTAMP),
                            CURRENT_TIMESTAMP)
                """, (user_id, username, first_name, last_name, user_id))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error tracking user {user_id}: {e}")
    
    async def track_interaction(self, user_id: int, action_type: str, details: Optional[str] = None) -> None:
        """Track a user interaction."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO interactions (user_id, action_type, details)
                    VALUES (?, ?, ?)
                """, (user_id, action_type, details))
                conn.commit()
        except Exception as e:
            logger.error(f"Error tracking interaction for user {user_id}: {e}")
    
    async def track_file_processing_start(self, user_id: int, file_name: str, 
                                        file_size_mb: float, file_type: str) -> int:
        """Track the start of file processing. Returns event ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO file_events (user_id, file_name, file_size_mb, file_type, status)
                    VALUES (?, ?, ?, ?, 'started')
                """, (user_id, file_name, file_size_mb, file_type))
                conn.commit()
                return cursor.lastrowid or -1
        except Exception as e:
            logger.error(f"Error tracking file processing start: {e}")
            return -1
    
    async def track_file_processing_complete(self, event_id: int, processing_time_seconds: float) -> None:
        """Track successful completion of file processing."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE file_events 
                    SET status = 'completed', processing_time_seconds = ?
                    WHERE id = ?
                """, (processing_time_seconds, event_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error tracking file processing completion: {e}")
    
    async def track_file_processing_failed(self, event_id: int, error_message: str) -> None:
        """Track failed file processing."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE file_events 
                    SET status = 'failed', error_message = ?
                    WHERE id = ?
                """, (error_message, event_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error tracking file processing failure: {e}")
    
    async def update_daily_stats(self) -> None:
        """Update daily statistics."""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get today's stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT user_id) as active_users,
                        COUNT(*) as files_processed,
                        SUM(file_size_mb) as total_file_size_mb,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_transcriptions,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_transcriptions
                    FROM file_events 
                    WHERE DATE(timestamp) = ?
                """, (today,))
                
                stats = cursor.fetchone()
                
                if stats:
                    cursor.execute("""
                        INSERT OR REPLACE INTO daily_stats 
                        (date, active_users, files_processed, total_file_size_mb, successful_transcriptions, failed_transcriptions, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (today, stats[0], stats[1], stats[2] or 0, stats[3], stats[4]))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error updating daily stats: {e}")
    
    def get_user_stats(self) -> Dict:
        """Get user statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total users
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]
                
                # Active users (last 7 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE last_seen >= datetime('now', '-7 days')
                """)
                active_users_7d = cursor.fetchone()[0]
                
                # Active users (last 30 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE last_seen >= datetime('now', '-30 days')
                """)
                active_users_30d = cursor.fetchone()[0]
                
                # New users (last 7 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE first_seen >= datetime('now', '-7 days')
                """)
                new_users_7d = cursor.fetchone()[0]
                
                return {
                    'total_users': total_users,
                    'active_users_7d': active_users_7d,
                    'active_users_30d': active_users_30d,
                    'new_users_7d': new_users_7d
                }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}
    
    def get_file_stats(self) -> Dict:
        """Get file processing statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total files processed
                cursor.execute("SELECT COUNT(*) FROM file_events")
                total_files = cursor.fetchone()[0]
                
                # Files processed in last 7 days
                cursor.execute("""
                    SELECT COUNT(*) FROM file_events 
                    WHERE timestamp >= datetime('now', '-7 days')
                """)
                files_7d = cursor.fetchone()[0]
                
                # Success rate
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful
                    FROM file_events
                """)
                total, successful = cursor.fetchone()
                success_rate = (successful / total * 100) if total > 0 else 0
                
                # Average file size
                cursor.execute("""
                    SELECT AVG(file_size_mb) FROM file_events
                """)
                avg_file_size = cursor.fetchone()[0] or 0
                
                # Average processing time
                cursor.execute("""
                    SELECT AVG(processing_time_seconds) FROM file_events 
                    WHERE status = 'completed' AND processing_time_seconds IS NOT NULL
                """)
                avg_processing_time = cursor.fetchone()[0] or 0
                
                return {
                    'total_files': total_files,
                    'files_7d': files_7d,
                    'success_rate': round(success_rate, 2),
                    'avg_file_size_mb': round(avg_file_size, 2),
                    'avg_processing_time_seconds': round(avg_processing_time, 2)
                }
        except Exception as e:
            logger.error(f"Error getting file stats: {e}")
            return {}
    
    def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Get top users by file count."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        u.user_id,
                        u.username,
                        u.first_name,
                        COUNT(f.id) as file_count,
                        AVG(f.file_size_mb) as avg_file_size,
                        u.first_seen,
                        u.last_seen
                    FROM users u
                    LEFT JOIN file_events f ON u.user_id = f.user_id
                    GROUP BY u.user_id
                    ORDER BY file_count DESC
                    LIMIT ?
                """, (limit,))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'file_count': row[3],
                        'avg_file_size_mb': round(row[4] or 0, 2),
                        'first_seen': row[5],
                        'last_seen': row[6]
                    })
                return results
        except Exception as e:
            logger.error(f"Error getting top users: {e}")
            return []
    
    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """Get daily statistics for the last N days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        date,
                        active_users,
                        files_processed,
                        total_file_size_mb,
                        successful_transcriptions,
                        failed_transcriptions
                    FROM daily_stats
                    WHERE date >= date('now', '-{} days')
                    ORDER BY date DESC
                """.format(days))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'date': row[0],
                        'active_users': row[1],
                        'files_processed': row[2],
                        'total_file_size_mb': round(row[3] or 0, 2),
                        'successful_transcriptions': row[4],
                        'failed_transcriptions': row[5]
                    })
                return results
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return []


# Global instance
_metrics_service = None

def get_metrics_service() -> MetricsService:
    """Get the global metrics service instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service