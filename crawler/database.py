"""Database operations for the Tübingen crawler."""

import duckdb
import threading
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

from .config import CrawlerConfig, DATABASE_SCHEMA


class DatabaseManager:
    """Manages database operations for the crawler."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.db_path = config.db_path
        self._connection = None
        self._lock = threading.Lock()
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the database and create tables."""
        with self._get_connection() as conn:
            # Check if errors table exists with the old schema
            try:
                result = conn.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'errors' AND column_name = 'id'
                """).fetchall()
                
                if result and result[0][1] == 'INTEGER':
                    # Check if it's using the old schema (no sequence)
                    try:
                        conn.execute("SELECT nextval('errors_id_seq')").fetchone()
                    except:
                        # No sequence exists - old schema detected
                        print("Detected old errors table schema. Migrating to new schema...")
                        self._migrate_errors_table(conn)
                    
            except Exception:
                # Table doesn't exist yet, which is fine
                pass
            
            # Check if urlsDB table exists but is missing the title column
            try:
                result = conn.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'urlsDB' AND column_name = 'title'
                """).fetchall()
                
                if not result:
                    # title column doesn't exist, need to add it
                    print("Detected urlsDB table missing title column. Adding title column...")
                    self._migrate_urlsdb_add_title(conn)
                    
            except Exception:
                # Table doesn't exist yet, which is fine
                pass
            
            for table_name, schema in DATABASE_SCHEMA.items():
                # Handle multi-statement schemas (like errors table with sequence)
                statements = [stmt.strip() for stmt in schema.split(';') if stmt.strip()]
                for statement in statements:
                    conn.execute(statement)
            conn.commit()
    
    def _migrate_errors_table(self, conn):
        """Migrate the errors table from old schema to new schema."""
        try:
            # Check if table exists and has data
            result = conn.execute("SELECT COUNT(*) FROM errors").fetchone()
            has_data = result[0] > 0 if result else False
            
            if has_data:
                # Backup existing data
                conn.execute("""
                    CREATE TABLE errors_backup AS 
                    SELECT url, error_type, error_message, status_code, timestamp 
                    FROM errors
                """)
                
                # Drop old table
                conn.execute("DROP TABLE errors")
                
                # Create new table with correct schema
                conn.execute(DATABASE_SCHEMA["errors"])
                
                # Restore data (id will be auto-generated)
                conn.execute("""
                    INSERT INTO errors (url, error_type, error_message, status_code, timestamp)
                    SELECT url, error_type, error_message, status_code, timestamp
                    FROM errors_backup
                """)
                
                # Drop backup table
                conn.execute("DROP TABLE errors_backup")
                print("✅ Successfully migrated errors table with data preserved")
            else:
                # No data, just recreate the table
                conn.execute("DROP TABLE errors")
                conn.execute(DATABASE_SCHEMA["errors"])
                print("✅ Successfully recreated errors table")
                
        except Exception as e:
            print(f"Warning: Could not migrate errors table: {e}")
            print("If you continue to have issues, you may need to delete the database file and start fresh.")
    
    def _migrate_urlsdb_add_title(self, conn):
        """Migrate the urlsDB table to add the title column."""
        try:
            # Check if table exists and has data
            result = conn.execute("SELECT COUNT(*) FROM urlsDB").fetchone()
            has_data = result[0] > 0 if result else False
            
            if has_data:
                # Backup existing data
                conn.execute("""
                    CREATE TABLE urlsDB_backup AS 
                    SELECT url, lastFetch, text, tueEngScore, linkingDepth, domainLinkingDepth, 
                           parentUrl, statusCode, contentType, lastModified, etag
                    FROM urlsDB
                """)
                
                # Drop old table
                conn.execute("DROP TABLE urlsDB")
                
                # Create new table with correct schema
                conn.execute("""
                    CREATE TABLE urlsDB (
                        url TEXT PRIMARY KEY,
                        lastFetch TIMESTAMP,
                        text TEXT,
                        title TEXT,
                        tueEngScore REAL,
                        linkingDepth INTEGER,
                        domainLinkingDepth INTEGER,
                        parentUrl TEXT,
                        statusCode INTEGER,
                        contentType TEXT,
                        lastModified TIMESTAMP,
                        etag TEXT
                    )
                """)
                
                # Restore data (title will be NULL for existing records)
                conn.execute("""
                    INSERT INTO urlsDB (url, lastFetch, text, title, tueEngScore, linkingDepth, domainLinkingDepth, 
                                       parentUrl, statusCode, contentType, lastModified, etag)
                    SELECT url, lastFetch, text, NULL, tueEngScore, linkingDepth, domainLinkingDepth, 
                           parentUrl, statusCode, contentType, lastModified, etag
                    FROM urlsDB_backup
                """)
                
                # Drop backup table
                conn.execute("DROP TABLE urlsDB_backup")
                print("✅ Successfully migrated urlsDB table with data preserved")
            else:
                # No data, just recreate the table
                conn.execute("DROP TABLE urlsDB")
                conn.execute("""
                    CREATE TABLE urlsDB (
                        url TEXT PRIMARY KEY,
                        lastFetch TIMESTAMP,
                        text TEXT,
                        title TEXT,
                        tueEngScore REAL,
                        linkingDepth INTEGER,
                        domainLinkingDepth INTEGER,
                        parentUrl TEXT,
                        statusCode INTEGER,
                        contentType TEXT,
                        lastModified TIMESTAMP,
                        etag TEXT
                    )
                """)
                print("✅ Successfully recreated urlsDB table")
                
        except Exception as e:
            print(f"Warning: Could not migrate urlsDB table: {e}")
            print("If you continue to have issues, you may need to delete the database file and start fresh.")
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with thread safety."""
        with self._lock:
            if self._connection is None:
                self._connection = duckdb.connect(self.db_path)
            yield self._connection
    
    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
    
    def insert_url(self, url: str, text: Optional[str] = None, title: Optional[str] = None, score: Optional[float] = None, 
                   linking_depth: Optional[int] = None, domain_linking_depth: Optional[int] = None,
                   parent_url: Optional[str] = None, status_code: Optional[int] = None,
                   content_type: Optional[str] = None, last_modified: Optional[datetime] = None,
                   etag: Optional[str] = None) -> bool:
        """Insert or update a URL in the database."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO urlsDB 
                    (url, lastFetch, text, title, tueEngScore, linkingDepth, domainLinkingDepth, 
                     parentUrl, statusCode, contentType, lastModified, etag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (url) DO UPDATE SET
                        lastFetch = excluded.lastFetch,
                        text = excluded.text,
                        title = excluded.title,
                        tueEngScore = excluded.tueEngScore,
                        linkingDepth = excluded.linkingDepth,
                        domainLinkingDepth = excluded.domainLinkingDepth,
                        parentUrl = excluded.parentUrl,
                        statusCode = excluded.statusCode,
                        contentType = excluded.contentType,
                        lastModified = excluded.lastModified,
                        etag = excluded.etag
                """, (url, datetime.now(), text, title, score, linking_depth, domain_linking_depth,
                      parent_url, status_code, content_type, last_modified, etag))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error inserting URL {url}: {e}")
            return False
    
    def get_url_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get information about a URL from the database."""
        try:
            with self._get_connection() as conn:
                result = conn.execute("""
                    SELECT * FROM urlsDB WHERE url = ?
                """, (url,)).fetchone()
                
                if result:
                    columns = [desc[0] for desc in conn.description]
                    return dict(zip(columns, result))
                return None
        except Exception as e:
            print(f"Error getting URL info for {url}: {e}")
            return None
    
    def is_url_crawled(self, url: str) -> bool:
        """Check if a URL has been crawled."""
        try:
            with self._get_connection() as conn:
                result = conn.execute("""
                    SELECT COUNT(*) FROM urlsDB WHERE url = ?
                """, (url,)).fetchone()
                return result[0] > 0
        except Exception as e:
            print(f"Error checking if URL crawled {url}: {e}")
            return False
    
    def add_to_frontier(self, url: str, schedule: float, delay: float, priority: float) -> bool:
        """Add a URL to the frontier."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO frontier (url, schedule, delay, priority)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (url) DO UPDATE SET
                        schedule = excluded.schedule,
                        delay = excluded.delay,
                        priority = excluded.priority
                """, (url, schedule, delay, priority))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding to frontier {url}: {e}")
            return False
    
    def get_frontier_urls(self, limit: int = 100) -> List[Tuple[str, float, float, float]]:
        """Get URLs from the frontier ordered by priority."""
        try:
            with self._get_connection() as conn:
                results = conn.execute("""
                    SELECT url, schedule, delay, priority 
                    FROM frontier 
                    ORDER BY priority DESC 
                    LIMIT ?
                """, (limit,)).fetchall()
                return results
        except Exception as e:
            print(f"Error getting frontier URLs: {e}")
            return []
    
    def remove_from_frontier(self, url: str) -> bool:
        """Remove a URL from the frontier."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM frontier WHERE url = ?", (url,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error removing from frontier {url}: {e}")
            return False
    
    def add_disallowed_url(self, url: str, reason: str) -> bool:
        """Add a URL to the disallowed list."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO disallowed (url, reason)
                    VALUES (?, ?)
                    ON CONFLICT (url) DO UPDATE SET
                        reason = excluded.reason
                """, (url, reason))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding disallowed URL {url}: {e}")
            return False
    
    def is_url_disallowed(self, url: str) -> bool:
        """Check if a URL is disallowed."""
        try:
            with self._get_connection() as conn:
                result = conn.execute("""
                    SELECT COUNT(*) FROM disallowed WHERE url = ?
                """, (url,)).fetchone()
                return result[0] > 0
        except Exception as e:
            print(f"Error checking disallowed URL {url}: {e}")
            return False
    
    def log_error(self, url: str, error_type: str, error_message: str, status_code: Optional[int] = None) -> bool:
        """Log an error to the database."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO errors (url, error_type, error_message, status_code)
                    VALUES (?, ?, ?, ?)
                """, (url, error_type, error_message, status_code))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error logging error for {url}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, int]:
        """Get crawling statistics."""
        try:
            with self._get_connection() as conn:
                stats = {}
                
                # Count of crawled URLs
                result = conn.execute("SELECT COUNT(*) FROM urlsDB").fetchone()
                stats['crawled_urls'] = result[0]
                
                # Count of frontier URLs
                result = conn.execute("SELECT COUNT(*) FROM frontier").fetchone()
                stats['frontier_urls'] = result[0]
                
                # Count of disallowed URLs
                result = conn.execute("SELECT COUNT(*) FROM disallowed").fetchone()
                stats['disallowed_urls'] = result[0]
                
                # Count of errors
                result = conn.execute("SELECT COUNT(*) FROM errors").fetchone()
                stats['errors'] = result[0]
                
                return stats
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}
    
    def export_to_csv(self, table_name: str, filename: str, columns: str = "*") -> bool:
        """Export a table to CSV."""
        try:
            with self._get_connection() as conn:
                conn.execute(f"""
                    COPY (SELECT {columns} FROM {table_name}) 
                    TO '{filename}' (FORMAT CSV, HEADER TRUE)
                """)
                return True
        except Exception as e:
            print(f"Error exporting {table_name} to CSV: {e}")
            return False
    
    def clear_frontier(self) -> bool:
        """Clear the frontier table."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM frontier")
                conn.commit()
                return True
        except Exception as e:
            print(f"Error clearing frontier: {e}")
            return False 