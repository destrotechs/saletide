# yourapp/templatetags/currency.py

from django import template

register = template.Library()

@register.filter
def currency_p(value):
    try:
        value = float(value)
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return "0.00"
