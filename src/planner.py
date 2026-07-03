# Planner logic for the Breakfast Orchestrator Agent

import json
from prompts import CONCIERGE_SYSTEM_PROMPT
from utils import generate_grocery_list, format_prep_summary

def run_concierge_agent(recipe_db_path):
    # 1. Load the database
    with open(recipe_db_path, 'r') as f:
        recipes = json.load(f)
    
    # 2. Logic simulation (In a full agent, you'd call your LLM API here)
    # For this test, we simulate an AI-generated plan based on your rules
    print("--- Generating 7-Day Breakfast Plan ---")
    
    # This is a sample output format your LLM will eventually generate
    # after being prompted with your constraints.
    sample_plan = [
        {"day_of_week": "Monday", "recipe_name": "Idli", "category": "Idli", "ingredients": ["Idli rice", "Urad dal", "Salt"], "youtube_search_url": "..."},
        {"day_of_week": "Tuesday", "recipe_name": "Podi Idli", "category": "Idli", "ingredients": ["Idli", "Idli podi"], "youtube_search_url": "..."}
    ]
    
    # 3. Use 'Hands' (utils) to process the data
    grocery_list = generate_grocery_list(sample_plan)
    prep_summary = format_prep_summary(sample_plan)
    
    print("\n--- Saturday Grocery List ---")
    print(grocery_list)
    print("\n--- YouTube Prep Summary ---")
    print(prep_summary)

if __name__ == "__main__":
    run_concierge_agent("../data/south_indian_breakfast_recipes.json")