# Helper utilities for the Breakfast Orchestrator Agent
import json

def generate_grocery_list(meal_plan):
    """Aggregates all ingredients from a 7-day meal plan into a unique shopping list."""
    grocery_list = set()
    for day in meal_plan:
        ingredients = day.get('ingredients', [])
        for item in ingredients:
            grocery_list.add(item.strip())
    return sorted(list(grocery_list))

def format_prep_summary(meal_plan):
    """Extracts recipes, their categories, and YouTube links for Saturday prep."""
    summary = []
    for day in meal_plan:
        summary.append({
            "day": day['day_of_week'],
            "recipe": day['recipe_name'],
            "youtube": day['youtube_search_url']
        })
    return summary

print("Utils logic initialized. Ready to process plan.")