# yourapp/templatetags/currency.py

from django import template

register = template.Library()

@register.filter
def currency(value, symbol="Ksh."):
    try:
        value = float(value)
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return f"0.00"
