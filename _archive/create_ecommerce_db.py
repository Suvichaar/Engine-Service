#!/usr/bin/env python3
"""
Script to create the e-commerce database schema.

Run this script to create all tables in your PostgreSQL database.

Usage:
    python scripts/create_ecommerce_db.py
"""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.persistence.ecommerce_models import create_all_tables, Base

# Database configuration for Azure PostgreSQL
DATABASE_CONFIG = {
    "host": "suvichaarpgrawstagedbserver.postgres.database.azure.com",
    "dbname": "postgres",
    "user": "suvichaarrawstage_db_admin",
    "password": "Thinkpure008",
    "port": 5432
}


def get_database_url() -> str:
    """Construct PostgreSQL database URL from config."""
    return (
        f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
        f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['dbname']}"
    )


def main():
    """Create all e-commerce tables in the database."""
    database_url = get_database_url()
    
    print("=" * 60)
    print("E-Commerce Database Schema Creation")
    print("=" * 60)
    print(f"\nConnecting to: {DATABASE_CONFIG['host']}")
    print(f"Database: {DATABASE_CONFIG['dbname']}")
    print(f"User: {DATABASE_CONFIG['user']}")
    print()
    
    # Show tables to be created
    print("Tables to be created:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")
    print()
    
    # Ask for confirmation
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    if response not in ["yes", "y"]:
        print("Aborted.")
        return
    
    print("\nCreating tables...")
    try:
        create_all_tables(database_url, echo=True)
        print("\n✓ All tables created successfully!")
    except Exception as e:
        print(f"\n✗ Error creating tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
