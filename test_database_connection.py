"""Test script to verify database connection and table creation."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings
from app.persistence.database import create_session_factory
from app.persistence.story_repository import Base, StoryORM

def test_database_connection():
    """Test database connection and table creation."""
    print("=" * 60)
    print("Testing Database Connection")
    print("=" * 60)
    
    try:
        # Load settings
        settings = get_settings()
        db_url = settings.database.url
        print(f"\n[INFO] Database URL: {db_url[:50]}...")  # Don't print full password
        
        # Create session factory
        print("\n[STEP 1] Creating session factory...")
        factory = create_session_factory(db_url, echo=False)
        print("[OK] Session factory created")
        
        # Get engine
        engine = factory.kw["bind"]
        print("\n[STEP 2] Creating tables...")
        Base.metadata.create_all(engine)
        print("[OK] Tables created successfully")
        
        # Test connection
        print("\n[STEP 3] Testing connection...")
        from sqlalchemy import text
        with factory() as session:
            # Try a simple query
            result = session.execute(text("SELECT 1")).scalar()
            print(f"[OK] Connection test passed (result: {result})")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Database connection and table creation successful!")
        print("=" * 60)
        print("\nTables created:")
        for table in Base.metadata.tables:
            print(f"  - {table}")
        
        return True
        
    except ImportError as e:
        print(f"\n[ERROR] Import error: {e}")
        print("\nPlease install psycopg[binary]:")
        print("  pip install 'psycopg[binary]>=3.2.0'")
        return False
    except Exception as e:
        print(f"\n[ERROR] Database connection failed: {e}")
        print(f"\nError type: {type(e).__name__}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1)

