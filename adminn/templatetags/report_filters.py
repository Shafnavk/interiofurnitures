from django import template

register = template.Library()

@register.filter
def sub(value, arg):
    """Subtract the arg from the value."""
    try:
        return value - arg
    except (ValueError, TypeError):
        try:
            return value or 0 - arg or 0
        except Exception:
            return 0
        
from django import template

register = template.Library()



@register.filter
def percentof(value, total):
    """Calculate what percentage of the total a value is"""
    try:
        if total == 0:
            return 0
        return round((value / total) * 100, 1)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Divides the value by the argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0