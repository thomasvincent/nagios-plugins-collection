"""Nagios plugins collection.

This package contains a collection of Nagios plugins for monitoring various systems.
Each plugin is designed to be used independently but follows a consistent interface.
"""

__all__ = [
    "check_monghealth",
    "check_hadoop",
    "check_website_status",
    "check_jobs",
    "check_etl",
    "check_dig",
    "check_ro_mounts",
    "check_procs",
]
