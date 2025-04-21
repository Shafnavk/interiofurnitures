from django import template

register = template.Library()




@register.filter
def get_range(value):
    return range(1, value+1)

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0 
    
@register.filter
def sub(value, arg):
    return value - arg
