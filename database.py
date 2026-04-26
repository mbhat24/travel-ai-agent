"""
Database Module - SQLite Persistence for Travel AI Agent
Provides persistent storage for users, trips, and conversations
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent / "data" / "travel_ai.db"
DB_PATH.parent.mkdir(exist_ok=True)

class Database:
    """SQLite database manager for Travel AI Agent"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    profile_data TEXT  -- JSON
                )
            """)
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Trips table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trips (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    budget REAL,
                    travelers INTEGER DEFAULT 1,
                    interests TEXT,  -- JSON array
                    itinerary TEXT,  -- Generated itinerary
                    budget_breakdown TEXT,  -- JSON
                    recommendations TEXT,  -- JSON array
                    status TEXT DEFAULT 'planned',  -- planned, active, completed, cancelled
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    session_id TEXT,
                    message TEXT NOT NULL,
                    response TEXT,
                    sentiment TEXT,  -- JSON
                    emergency_detected BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            
            # Bookings table (for future integration)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    booking_type TEXT NOT NULL,  -- flight, hotel, activity
                    provider TEXT,
                    confirmation_code TEXT,
                    booking_data TEXT,  -- JSON
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id)")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    # User operations
    def create_user(self, email: str, username: str, hashed_password: str, profile_data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Create a new user"""
        try:
            user_id = str(uuid.uuid4())
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO users (id, email, username, hashed_password, profile_data)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, email, username, hashed_password, json.dumps(profile_data or {}))
                )
                conn.commit()
                return self.get_user_by_id(user_id)
        except sqlite3.IntegrityError:
            logger.warning(f"User with email {email} already exists")
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """Update user fields"""
        allowed_fields = ['username', 'is_active', 'profile_data']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        # Handle JSON fields
        if 'profile_data' in updates and isinstance(updates['profile_data'], dict):
            updates['profile_data'] = json.dumps(updates['profile_data'])
        
        updates['updated_at'] = datetime.utcnow().isoformat()
        
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0
    
    # Session operations
    def create_session(self, user_id: str, token: str, expires_days: int = 7) -> Optional[str]:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (?, ?, ?, ?)",
                (session_id, user_id, token, expires_at.isoformat())
            )
            conn.commit()
            return session_id
    
    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Get session by token"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions WHERE token = ? AND expires_at > ?",
                (token, datetime.utcnow().isoformat())
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
            conn.commit()
            return cursor.rowcount
    
    # Trip operations
    def create_trip(self, user_id: str, destination: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Create a new trip"""
        trip_id = str(uuid.uuid4())
        
        # Handle JSON fields
        interests = json.dumps(kwargs.get('interests', [])) if isinstance(kwargs.get('interests'), list) else kwargs.get('interests', '[]')
        budget_breakdown = json.dumps(kwargs.get('budget_breakdown', {})) if isinstance(kwargs.get('budget_breakdown'), dict) else kwargs.get('budget_breakdown', '{}')
        recommendations = json.dumps(kwargs.get('recommendations', [])) if isinstance(kwargs.get('recommendations'), list) else kwargs.get('recommendations', '[]')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO trips (id, user_id, destination, start_date, end_date, budget, 
                    travelers, interests, itinerary, budget_breakdown, recommendations, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trip_id, user_id, destination,
                 kwargs.get('start_date'), kwargs.get('end_date'),
                 kwargs.get('budget'), kwargs.get('travelers', 1),
                 interests, kwargs.get('itinerary', ''),
                 budget_breakdown, recommendations,
                 kwargs.get('status', 'planned'))
            )
            conn.commit()
            return self.get_trip_by_id(trip_id)
    
    def get_trip_by_id(self, trip_id: str) -> Optional[Dict[str, Any]]:
        """Get trip by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
    
    def get_user_trips(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all trips for a user"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM trips WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                    (user_id, status)
                )
            else:
                cursor.execute(
                    "SELECT * FROM trips WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                )
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def update_trip(self, trip_id: str, **kwargs) -> bool:
        """Update trip fields"""
        allowed_fields = ['destination', 'start_date', 'end_date', 'budget', 'travelers',
                         'interests', 'itinerary', 'budget_breakdown', 'recommendations', 'status']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        # Handle JSON fields
        for field in ['interests', 'budget_breakdown', 'recommendations']:
            if field in updates and isinstance(updates[field], (list, dict)):
                updates[field] = json.dumps(updates[field])
        
        updates['updated_at'] = datetime.utcnow().isoformat()
        
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [trip_id]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE trips SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_trip(self, trip_id: str) -> bool:
        """Delete a trip"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Conversation operations
    def save_conversation(self, message: str, response: Optional[str] = None,
                         user_id: Optional[str] = None, session_id: Optional[str] = None,
                         sentiment: Optional[Dict] = None, emergency_detected: bool = False) -> str:
        """Save a conversation entry"""
        conv_id = str(uuid.uuid4())
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO conversations 
                    (id, user_id, session_id, message, response, sentiment, emergency_detected)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (conv_id, user_id, session_id, message, response,
                 json.dumps(sentiment) if sentiment else None, emergency_detected)
            )
            conn.commit()
            return conv_id
    
    def get_conversation_history(self, user_id: Optional[str] = None, 
                                  session_id: Optional[str] = None,
                                  limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """SELECT * FROM conversations 
                       WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
                    (user_id, limit)
                )
            elif session_id:
                cursor.execute(
                    """SELECT * FROM conversations 
                       WHERE session_id = ? ORDER BY created_at DESC LIMIT ?""",
                    (session_id, limit)
                )
            else:
                cursor.execute(
                    """SELECT * FROM conversations 
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,)
                )
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    # Statistics
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            for table in ['users', 'sessions', 'trips', 'conversations', 'bookings']:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            
            return stats
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite row to dictionary"""
        result = dict(row)
        
        # Parse JSON fields
        json_fields = ['profile_data', 'interests', 'budget_breakdown', 
                      'recommendations', 'booking_data', 'sentiment']
        for field in json_fields:
            if field in result and result[field]:
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        return result

# Global database instance
db = Database()
