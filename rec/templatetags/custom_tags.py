from django import template

register = template.Library()


@register.filter
def in_list(value, arg):
    """
    Usage: {{ value|in_list:"a,b,c" }}
    Returns True if value is in the comma-separated string.
    """
    if not value or not arg:
        return False
    return str(value) in [item.strip() for item in arg.split(',')]
