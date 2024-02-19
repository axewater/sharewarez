# modules/filters.py

def format_size(size):
    if size >= 1024:
        size_in_gb = size / 1024
        return f"{size_in_gb:.2f} GB"
    else:
        return f"{size:.0f} MB"

def setup_filters(app):
    app.jinja_env.filters['format_size'] = format_size
