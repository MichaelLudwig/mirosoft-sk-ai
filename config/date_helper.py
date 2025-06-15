from datetime import datetime, timedelta
import re


def calculate_date_filter(query: str) -> str:
    """
    Calculate date filters for Graph API based on natural language
    Returns the date in ISO 8601 format for Graph API filters
    """
    today = datetime.now()
    query_lower = query.lower()
    
    # Patterns for relative date calculations
    if "heute" in query_lower or "today" in query_lower:
        return today.strftime("%Y-%m-%dT00:00:00Z")
    
    elif "gestern" in query_lower or "yesterday" in query_lower:
        yesterday = today - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%dT00:00:00Z")
    
    elif "letzte woche" in query_lower or "last week" in query_lower:
        last_week = today - timedelta(days=7)
        return last_week.strftime("%Y-%m-%dT00:00:00Z")
    
    elif "letzten monat" in query_lower or "last month" in query_lower:
        last_month = today - timedelta(days=30)
        return last_month.strftime("%Y-%m-%dT00:00:00Z")
    
    elif "letztes jahr" in query_lower or "last year" in query_lower:
        last_year = today - timedelta(days=365)
        return last_year.strftime("%Y-%m-%dT00:00:00Z")
    
    # Pattern für "letzten X Tage"
    days_match = re.search(r"letzten?\s+(\d+)\s+tage?", query_lower)
    if days_match:
        days = int(days_match.group(1))
        target_date = today - timedelta(days=days)
        return target_date.strftime("%Y-%m-%dT00:00:00Z")
    
    # Pattern für "letzten X Wochen"
    weeks_match = re.search(r"letzten?\s+(\d+)\s+wochen?", query_lower)
    if weeks_match:
        weeks = int(weeks_match.group(1))
        target_date = today - timedelta(weeks=weeks)
        return target_date.strftime("%Y-%m-%dT00:00:00Z")
    
    # Pattern für "letzten X Monate"
    months_match = re.search(r"letzten?\s+(\d+)\s+monate?", query_lower)
    if months_match:
        months = int(months_match.group(1))
        target_date = today - timedelta(days=months*30)  # Approximation
        return target_date.strftime("%Y-%m-%dT00:00:00Z")
    
    # Default: return today's date
    return today.strftime("%Y-%m-%dT00:00:00Z")


def enhance_prompt_with_date(prompt: str) -> str:
    """
    Enhance the prompt with calculated dates for better Graph API generation
    """
    # Check if prompt contains relative date references
    date_keywords = ["heute", "gestern", "letzte", "letzten", "today", "yesterday", "last"]
    
    if any(keyword in prompt.lower() for keyword in date_keywords):
        calculated_date = calculate_date_filter(prompt)
        # Add the calculated date as a hint to the prompt
        return f"{prompt}\n[Hinweis: Verwende Datum >= {calculated_date} für Zeitfilter]"
    
    return prompt