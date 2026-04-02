#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

# demo_init лежит в examples/sdk-demos/python/
_PY_DEMOS = Path(__file__).resolve().parent.parent
if str(_PY_DEMOS) not in sys.path:
    sys.path.insert(0, str(_PY_DEMOS))


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_mvp.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install it and ensure it's on PYTHONPATH."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
