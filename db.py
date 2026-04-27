import os
from contextlib import contextmanager
import mysql.connector
from mysql.connector import pooling

_pool = None


def get_config():
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "managment_db"),
        "autocommit": False,
    }


def get_pool():
    global _pool
    if _pool is None:
        cfg = get_config()
        _pool = pooling.MySQLConnectionPool(
            pool_name="construction_pool",
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            **cfg,
        )
    return _pool


@contextmanager
def get_conn():
    conn = get_pool().get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(dictionary=True):
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=dictionary)
        try:
            yield cursor
        finally:
            try:
                while cursor.nextset():
                    pass
            except Exception:
                pass
            cursor.close()
