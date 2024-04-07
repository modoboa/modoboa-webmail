#!/usr/bin/env python

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as e:
        raise ImportError(
            "Failed to import Django. Make sure Django is installed and "
            "available on your PYTHONPATH, or activate a virtual environment."
        ) from e

    execute_from_command_line(sys.argv)
