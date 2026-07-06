from collections import defaultdict
import json
import os
import difflib

RECIPES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "south_indian_breakfast_recipes.json")

def load_recipes():
    """Loads all recipes from the database."""
    try:
        with open(RECIPES_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def standardize_ingredient(name):
    """Standardizes ingredient names to merge semantically identical inputs (e.g. oils, salts)."""
    name_lower = name.lower().strip()
    
    # Filter out water as a utility item
    if name_lower in ["water", "water (optional)", "water (as needed)"]:
        return None
        
    if "eno fruit salt" in name_lower or "eno" in name_lower:
        return "Eno / Fruit Salt"
    elif "salt" in name_lower:
        return "Salt"
    elif "oil" in name_lower or "ghee" in name_lower:
        return "Oil / Ghee"
    elif "chilli" in name_lower or "chili" in name_lower:
        if "red" in name_lower:
            return "Red Chillies"
        else:
            return "Green Chillies"
    elif "coriander" in name_lower:
        return "Coriander Leaves"
    elif "curry" in name_lower:
        return "Curry Leaves"
    elif "mustard" in name_lower:
        return "Mustard Seeds"
    elif "cumin" in name_lower:
        return "Cumin Seeds"
    elif "onion" in name_lower:
        return "Onions"
    elif "ginger" in name_lower:
        return "Ginger"
    elif "garlic" in name_lower:
        return "Garlic"
    elif "potato" in name_lower:
        return "Potatoes"
    elif "cashew" in name_lower:
        return "Cashew Nuts"
    elif "tomato" in name_lower:
        return "Tomatoes"
    elif "coconut" in name_lower:
        return "Grated Coconut"
    elif "rice" in name_lower:
        if "flour" in name_lower:
            return "Rice Flour"
        else:
            return "Rice"
    elif "urad" in name_lower:
        return "Urad Dal"
    elif "chana" in name_lower:
        return "Chana Dal"
    elif "moong" in name_lower:
        return "Moong Dal"
    elif "toor" in name_lower:
        return "Toor Dal"
    elif "semolina" in name_lower or "rava" in name_lower or "sooji" in name_lower:
        return "Rava (Semolina)"
    elif "poha" in name_lower:
        return "Poha (Flattened Rice)"
    elif "fenugreek" in name_lower or "methi" in name_lower:
        return "Fenugreek Seeds (Methi)"
    elif "asafoetida" in name_lower or "hing" in name_lower:
        return "Asafoetida (Hing)"
        
    return name.title().strip()

def aggregate_grocery_list(plan):
    """
    Aggregates ingredients from a plan, applying standardization rules.
    Handles plans containing full recipe details or plans containing just recipe names by looking them up in the DB.
    """
    recipes_db = {r.get("recipe_name"): r for r in load_recipes() if r.get("recipe_name")}
    all_ingredients = set()

    for entry in plan:
        ingredients = entry.get("ingredients")
        if not ingredients:
            recipe_name = entry.get("recipe_name")
            recipe = recipes_db.get(recipe_name, {})
            ingredients = recipe.get("ingredients", [])
        
        for ingredient in ingredients:
            std = standardize_ingredient(ingredient)
            if std:
                all_ingredients.add(std)
                
    return sorted(list(all_ingredients))

def find_best_recipe_match(query, recipes):
    """
    Finds the closest recipe match in the database for a given user query.
    Fuzzy matches words to be typo-tolerant.
    """
    query_lower = query.lower()
    
    # Try exact substring matching first
    for r in recipes:
        name = r.get("recipe_name", "")
        if name.lower() in query_lower:
            return name
            
    # Try fuzzy matching using SequenceMatcher
    best_match = None
    best_score = 0.0
    
    for r in recipes:
        name = r.get("recipe_name", "")
        # Compare name against query segments
        score = difflib.SequenceMatcher(None, name.lower(), query_lower).ratio()
        if score > best_score:
            best_score = score
            best_match = name
            
    # If confidence is reasonably high, return it
    if best_score > 0.45:
        return best_match
        
    return None