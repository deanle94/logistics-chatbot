"""Data access layer.

The only layer permitted to import SQLAlchemy or a database driver. Everything that
touches PostgreSQL - models, engine, seeding, connectivity probes - lives here.
"""
