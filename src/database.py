"""SQLite database for storing post metadata and tracking downloads."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PostRecord:
    id: str
    subreddit: str
    author: str
    title: str
    url: str
    media_url: Optional[str]
    media_type: Optional[str]
    score: int
    created_utc: float
    downloaded_at: Optional[datetime]
    local_path: Optional[str]
    file_hash: Optional[str]
    permalink: Optional[str] = None  # Reddit permalink for Immich
    source_type: Optional[str] = None  # 'subreddit' or 'user'
    flair: Optional[str] = None  # Post flair for tagging


class Database:
    """SQLite database wrapper for tracking downloaded posts."""

    def __init__(self, db_path: str = "media.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    subreddit TEXT NOT NULL,
                    author TEXT,
                    title TEXT,
                    url TEXT NOT NULL,
                    media_url TEXT,
                    media_type TEXT,
                    score INTEGER DEFAULT 0,
                    created_utc REAL,
                    downloaded_at TIMESTAMP,
                    local_path TEXT,
                    file_hash TEXT,
                    permalink TEXT,
                    source_type TEXT,
                    flair TEXT
                )
            """)
            # Favorites table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    post_id TEXT PRIMARY KEY,
                    favorited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts(id)
                )
            """)
            # Add new columns if they don't exist (migration)
            try:
                conn.execute("ALTER TABLE posts ADD COLUMN permalink TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE posts ADD COLUMN source_type TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE posts ADD COLUMN flair TEXT")
            except sqlite3.OperationalError:
                pass
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_subreddit ON posts(subreddit)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_hash ON posts(file_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_downloaded ON posts(downloaded_at)"
            )
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def post_exists(self, post_id: str) -> bool:
        """Check if a post has already been processed."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM posts WHERE id = ?", (post_id,)
            )
            return cursor.fetchone() is not None

    def hash_exists(self, file_hash: str) -> Optional[str]:
        """Check if a file with this hash already exists. Returns local_path if found."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT local_path FROM posts WHERE file_hash = ?", (file_hash,)
            )
            row = cursor.fetchone()
            return row["local_path"] if row else None

    def add_post(self, post: PostRecord) -> None:
        """Add or update a post record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO posts
                (id, subreddit, author, title, url, media_url, media_type,
                 score, created_utc, downloaded_at, local_path, file_hash,
                 permalink, source_type, flair)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.id,
                    post.subreddit,
                    post.author,
                    post.title,
                    post.url,
                    post.media_url,
                    post.media_type,
                    post.score,
                    post.created_utc,
                    post.downloaded_at,
                    post.local_path,
                    post.file_hash,
                    post.permalink,
                    post.source_type,
                    post.flair,
                ),
            )
            conn.commit()

    def mark_downloaded(
        self, post_id: str, local_path: str, file_hash: str
    ) -> None:
        """Mark a post as downloaded with file info."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE posts
                SET downloaded_at = ?, local_path = ?, file_hash = ?
                WHERE id = ?
                """,
                (datetime.now(), local_path, file_hash, post_id),
            )
            conn.commit()

    def get_post(self, post_id: str) -> Optional[PostRecord]:
        """Get a post record by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE id = ?", (post_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PostRecord(
                id=row["id"],
                subreddit=row["subreddit"],
                author=row["author"],
                title=row["title"],
                url=row["url"],
                media_url=row["media_url"],
                media_type=row["media_type"],
                score=row["score"],
                created_utc=row["created_utc"],
                downloaded_at=row["downloaded_at"],
                local_path=row["local_path"],
                file_hash=row["file_hash"],
                permalink=row["permalink"] if "permalink" in row.keys() else None,
                source_type=row["source_type"] if "source_type" in row.keys() else None,
                flair=row["flair"] if "flair" in row.keys() else None,
            )

    def get_all_downloaded(self) -> list[PostRecord]:
        """Get all downloaded posts for migration."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM posts WHERE downloaded_at IS NOT NULL"
            )
            posts = []
            for row in cursor.fetchall():
                posts.append(PostRecord(
                    id=row["id"],
                    subreddit=row["subreddit"],
                    author=row["author"],
                    title=row["title"],
                    url=row["url"],
                    media_url=row["media_url"],
                    media_type=row["media_type"],
                    score=row["score"],
                    created_utc=row["created_utc"],
                    downloaded_at=row["downloaded_at"],
                    local_path=row["local_path"],
                    file_hash=row["file_hash"],
                    permalink=row["permalink"] if "permalink" in row.keys() else None,
                    source_type=row["source_type"] if "source_type" in row.keys() else None,
                    flair=row["flair"] if "flair" in row.keys() else None,
                ))
            return posts

    def update_local_path(self, post_id: str, new_path: str) -> None:
        """Update local_path for a post (used in migration)."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE posts SET local_path = ? WHERE id = ?",
                (new_path, post_id)
            )
            conn.commit()

    def get_stats(self) -> dict:
        """Get collection statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            downloaded = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE downloaded_at IS NOT NULL"
            ).fetchone()[0]

            # Group by source: subreddits as "r/name", users as "u/name"
            by_source = {}

            # Downloads from subreddits
            subreddit_counts = conn.execute(
                """
                SELECT subreddit, COUNT(*)
                FROM posts
                WHERE downloaded_at IS NOT NULL
                  AND (source_type = 'subreddit' OR source_type IS NULL)
                GROUP BY subreddit
                """
            ).fetchall()
            for name, count in subreddit_counts:
                by_source[f"r/{name}"] = count

            # Downloads from users (group by author)
            user_counts = conn.execute(
                """
                SELECT author, COUNT(*)
                FROM posts
                WHERE downloaded_at IS NOT NULL
                  AND source_type = 'user'
                  AND author IS NOT NULL
                GROUP BY author
                """
            ).fetchall()
            for name, count in user_counts:
                by_source[f"u/{name}"] = count

            by_type = dict(
                conn.execute(
                    """
                    SELECT media_type, COUNT(*)
                    FROM posts
                    WHERE downloaded_at IS NOT NULL AND media_type IS NOT NULL
                    GROUP BY media_type
                    """
                ).fetchall()
            )

        return {
            "total_posts": total,
            "downloaded": downloaded,
            "by_source": by_source,
            "by_type": by_type,
        }

    def get_enhanced_stats(self) -> dict:
        """Get enhanced statistics for dashboard."""
        from datetime import datetime, timedelta

        with self._get_connection() as conn:
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            month_start = today_start - timedelta(days=30)

            # Format dates for SQLite comparison (space separator, not 'T')
            today_str = today_start.strftime('%Y-%m-%d %H:%M:%S')
            week_str = week_start.strftime('%Y-%m-%d %H:%M:%S')
            month_str = month_start.strftime('%Y-%m-%d %H:%M:%S')

            # Downloads by period
            downloads_today = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE downloaded_at >= ?",
                (today_str,)
            ).fetchone()[0]

            downloads_week = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE downloaded_at >= ?",
                (week_str,)
            ).fetchone()[0]

            downloads_month = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE downloaded_at >= ?",
                (month_str,)
            ).fetchone()[0]

            # Average score
            avg_score = conn.execute(
                "SELECT AVG(score) FROM posts WHERE downloaded_at IS NOT NULL AND score IS NOT NULL"
            ).fetchone()[0] or 0

            # Unique authors
            unique_authors = conn.execute(
                "SELECT COUNT(DISTINCT author) FROM posts WHERE downloaded_at IS NOT NULL AND author IS NOT NULL"
            ).fetchone()[0]

            # Favorites count
            favorites_count = conn.execute(
                "SELECT COUNT(*) FROM favorites"
            ).fetchone()[0]

            # Last download
            last_download = conn.execute(
                "SELECT downloaded_at FROM posts WHERE downloaded_at IS NOT NULL ORDER BY downloaded_at DESC LIMIT 1"
            ).fetchone()
            last_download = last_download[0] if last_download else None

            # First download (to calculate avg/day)
            first_download = conn.execute(
                "SELECT downloaded_at FROM posts WHERE downloaded_at IS NOT NULL ORDER BY downloaded_at ASC LIMIT 1"
            ).fetchone()

            total_downloaded = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE downloaded_at IS NOT NULL"
            ).fetchone()[0]

            # Calculate average per day
            avg_per_day = 0
            if first_download and first_download[0]:
                try:
                    first_date = datetime.fromisoformat(first_download[0].replace('Z', '+00:00'))
                    days_active = max((now - first_date.replace(tzinfo=None)).days, 1)
                    avg_per_day = round(total_downloaded / days_active, 1)
                except:
                    avg_per_day = 0

            # Top 10 authors
            top_authors = conn.execute(
                """
                SELECT author, COUNT(*) as count
                FROM posts
                WHERE downloaded_at IS NOT NULL AND author IS NOT NULL AND author != 'deleted' AND author != '[deleted]'
                GROUP BY author
                ORDER BY count DESC
                LIMIT 10
                """
            ).fetchall()

            # Downloads trend (last 14 days)
            trend_data = []
            for i in range(13, -1, -1):
                day = today_start - timedelta(days=i)
                day_end = day + timedelta(days=1)
                day_str = day.strftime('%Y-%m-%d %H:%M:%S')
                day_end_str = day_end.strftime('%Y-%m-%d %H:%M:%S')
                count = conn.execute(
                    "SELECT COUNT(*) FROM posts WHERE downloaded_at >= ? AND downloaded_at < ?",
                    (day_str, day_end_str)
                ).fetchone()[0]
                trend_data.append({
                    "date": day.strftime("%m/%d"),
                    "count": count
                })

        return {
            "downloads_today": downloads_today,
            "downloads_week": downloads_week,
            "downloads_month": downloads_month,
            "avg_score": round(avg_score, 1),
            "unique_authors": unique_authors,
            "favorites_count": favorites_count,
            "last_download": last_download,
            "avg_per_day": avg_per_day,
            "top_authors": [{"author": a, "count": c} for a, c in top_authors],
            "trend": trend_data
        }

    def get_recent_downloads(self, limit: int = 10) -> list[dict]:
        """Get most recent downloads."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, subreddit, author, title, media_type, score,
                       local_path, downloaded_at, permalink
                FROM posts
                WHERE downloaded_at IS NOT NULL AND local_path IS NOT NULL
                ORDER BY downloaded_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_media_files(self, limit: int = 50, offset: int = 0,
                        subreddit: str = None, media_type: str = None,
                        sort: str = "newest") -> list[dict]:
        """Get media files with optional filtering and sorting.

        Args:
            sort: 'newest' (default), 'oldest', 'score_high', 'score_low'
        """
        with self._get_connection() as conn:
            query = """
                SELECT id, subreddit, author, title, media_type, score,
                       local_path, downloaded_at, permalink, created_utc
                FROM posts
                WHERE downloaded_at IS NOT NULL AND local_path IS NOT NULL
            """
            params = []

            if subreddit:
                query += " AND LOWER(subreddit) = LOWER(?)"
                params.append(subreddit)

            if media_type:
                query += " AND media_type = ?"
                params.append(media_type)

            # Apply sorting
            if sort == "oldest":
                query += " ORDER BY created_utc ASC"
            elif sort == "score_high":
                query += " ORDER BY score DESC"
            elif sort == "score_low":
                query += " ORDER BY score ASC"
            else:  # newest (default)
                query += " ORDER BY created_utc DESC"

            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_total_media_count(self, subreddit: str = None, media_type: str = None) -> int:
        """Get total count of media files with optional filtering."""
        with self._get_connection() as conn:
            query = """
                SELECT COUNT(*)
                FROM posts
                WHERE downloaded_at IS NOT NULL AND local_path IS NOT NULL
            """
            params = []

            if subreddit:
                query += " AND LOWER(subreddit) = LOWER(?)"
                params.append(subreddit)

            if media_type:
                query += " AND media_type = ?"
                params.append(media_type)

            return conn.execute(query, params).fetchone()[0]

    def get_all_subreddits(self) -> list[str]:
        """Get list of all subreddits with downloaded content."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT subreddit
                FROM posts
                WHERE downloaded_at IS NOT NULL
                ORDER BY subreddit
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def get_posts_by_authors(self, authors: list[str]) -> list[PostRecord]:
        """Get all downloaded posts from specific authors (case-insensitive)."""
        if not authors:
            return []

        with self._get_connection() as conn:
            # Create placeholders for IN clause
            placeholders = ','.join('?' * len(authors))
            # Convert authors to lowercase for case-insensitive matching
            authors_lower = [a.lower() for a in authors]

            cursor = conn.execute(
                f"""
                SELECT * FROM posts
                WHERE LOWER(author) IN ({placeholders})
                  AND local_path IS NOT NULL
                  AND downloaded_at IS NOT NULL
                """,
                authors_lower
            )

            posts = []
            for row in cursor.fetchall():
                posts.append(PostRecord(
                    id=row["id"],
                    subreddit=row["subreddit"],
                    author=row["author"],
                    title=row["title"],
                    url=row["url"],
                    media_url=row["media_url"],
                    media_type=row["media_type"],
                    score=row["score"],
                    created_utc=row["created_utc"],
                    downloaded_at=row["downloaded_at"],
                    local_path=row["local_path"],
                    file_hash=row["file_hash"],
                    permalink=row["permalink"] if "permalink" in row.keys() else None,
                    source_type=row["source_type"] if "source_type" in row.keys() else None,
                    flair=row["flair"] if "flair" in row.keys() else None,
                ))
            return posts

    def count_posts_by_authors(self, authors: list[str]) -> int:
        """Count downloaded posts from specific authors (case-insensitive)."""
        if not authors:
            return 0

        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(authors))
            authors_lower = [a.lower() for a in authors]

            cursor = conn.execute(
                f"""
                SELECT COUNT(*) FROM posts
                WHERE LOWER(author) IN ({placeholders})
                  AND local_path IS NOT NULL
                  AND downloaded_at IS NOT NULL
                """,
                authors_lower
            )
            return cursor.fetchone()[0]

    def get_posts_by_subreddits(self, subreddits: list[str]) -> list[PostRecord]:
        """Get all downloaded posts from specific subreddits (case-insensitive)."""
        if not subreddits:
            return []

        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(subreddits))
            subreddits_lower = [s.lower() for s in subreddits]

            cursor = conn.execute(
                f"""
                SELECT * FROM posts
                WHERE LOWER(subreddit) IN ({placeholders})
                  AND local_path IS NOT NULL
                  AND downloaded_at IS NOT NULL
                """,
                subreddits_lower
            )

            posts = []
            for row in cursor.fetchall():
                posts.append(PostRecord(
                    id=row["id"],
                    subreddit=row["subreddit"],
                    author=row["author"],
                    title=row["title"],
                    url=row["url"],
                    media_url=row["media_url"],
                    media_type=row["media_type"],
                    score=row["score"],
                    created_utc=row["created_utc"],
                    downloaded_at=row["downloaded_at"],
                    local_path=row["local_path"],
                    file_hash=row["file_hash"],
                    permalink=row["permalink"] if "permalink" in row.keys() else None,
                    source_type=row["source_type"] if "source_type" in row.keys() else None,
                    flair=row["flair"] if "flair" in row.keys() else None,
                ))
            return posts

    def count_posts_by_subreddits(self, subreddits: list[str]) -> int:
        """Count downloaded posts from specific subreddits (case-insensitive)."""
        if not subreddits:
            return 0

        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(subreddits))
            subreddits_lower = [s.lower() for s in subreddits]

            cursor = conn.execute(
                f"""
                SELECT COUNT(*) FROM posts
                WHERE LOWER(subreddit) IN ({placeholders})
                  AND local_path IS NOT NULL
                  AND downloaded_at IS NOT NULL
                """,
                subreddits_lower
            )
            return cursor.fetchone()[0]

    # Favorites methods

    def add_favorite(self, post_id: str) -> bool:
        """Add a post to favorites. Returns True if added, False if already exists."""
        with self._get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO favorites (post_id) VALUES (?)",
                    (post_id,)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def remove_favorite(self, post_id: str) -> bool:
        """Remove a post from favorites. Returns True if removed."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM favorites WHERE post_id = ?",
                (post_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def is_favorite(self, post_id: str) -> bool:
        """Check if a post is favorited."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM favorites WHERE post_id = ?",
                (post_id,)
            )
            return cursor.fetchone() is not None

    def get_favorites(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Get all favorited posts with their info."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT p.id, p.subreddit, p.author, p.title, p.media_type,
                       p.score, p.local_path, p.downloaded_at, p.permalink,
                       p.created_utc, f.favorited_at
                FROM favorites f
                JOIN posts p ON f.post_id = p.id
                ORDER BY f.favorited_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            return [dict(row) for row in cursor.fetchall()]

    def count_favorites(self) -> int:
        """Count total favorites."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM favorites")
            return cursor.fetchone()[0]

    def get_favorite_authors(self) -> list[str]:
        """Get unique authors from favorited posts."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT p.author
                FROM favorites f
                JOIN posts p ON f.post_id = p.id
                WHERE p.author IS NOT NULL
                  AND p.author != '[deleted]'
                  AND p.author != 'AutoModerator'
                ORDER BY p.author
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def get_media_by_authors(
        self,
        authors: list[str],
        limit: int = 50,
        offset: int = 0,
        subreddit: str = None,
        media_type: str = None
    ) -> list[dict]:
        """Get media files from specific authors."""
        if not authors:
            return []

        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(authors))
            authors_lower = [a.lower() for a in authors]

            query = f"""
                SELECT id, subreddit, author, title, media_type, score,
                       local_path, downloaded_at, permalink, created_utc
                FROM posts
                WHERE LOWER(author) IN ({placeholders})
                  AND local_path IS NOT NULL
                  AND downloaded_at IS NOT NULL
            """
            params = list(authors_lower)

            if subreddit:
                query += " AND LOWER(subreddit) = ?"
                params.append(subreddit.lower())

            if media_type:
                query += " AND media_type = ?"
                params.append(media_type)

            query += " ORDER BY downloaded_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def count_media_by_authors(
        self,
        authors: list[str],
        subreddit: str = None,
        media_type: str = None
    ) -> int:
        """Count media files from specific authors."""
        if not authors:
            return 0

        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(authors))
            authors_lower = [a.lower() for a in authors]

            query = f"""
                SELECT COUNT(*) FROM posts
                WHERE LOWER(author) IN ({placeholders})
                  AND local_path IS NOT NULL
                  AND downloaded_at IS NOT NULL
            """
            params = list(authors_lower)

            if subreddit:
                query += " AND LOWER(subreddit) = ?"
                params.append(subreddit.lower())

            if media_type:
                query += " AND media_type = ?"
                params.append(media_type)

            cursor = conn.execute(query, params)
            return cursor.fetchone()[0]
