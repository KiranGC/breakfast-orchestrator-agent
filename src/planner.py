import json
import os
import random
from google import genai
from google.genai import types
from src.prompts import CONCIERGE_SYSTEM_PROMPT, CHAT_AGENT_SYSTEM_PROMPT
from src.utils import find_best_recipe_match

RECIPES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "south_indian_breakfast_recipes.json")

class BreakfastPlanner:
    def __init__(self):
        self.recipes = self._load_recipes()

    def _load_recipes(self):
        try:
            with open(RECIPES_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            return []

    def validate_plan(self, plan, disliked_recipes=None, full_context_plan=None, target_offset=0):
        """
        Validates the refined constraints:
        1. No recipe in disliked_recipes is included.
        2. Refined batter category cooling-off constraint:
           If Day N uses a batter category (e.g. Dosa), Day N+1, N+2, and N+3 cannot use a DIFFERENT batter category.
           Repeats of the same batter category (Dosa -> Dosa) are allowed.
        3. 15-day recipe cooling-off constraint:
           The same recipe cannot appear within a 15-day window in the full 21-day timeline.
        """
        disliked = set(disliked_recipes or [])
        
        # 1 & 2: Local weekly check
        last_batter_idx = -10
        last_batter_category = None
        
        for idx, entry in enumerate(plan):
            recipe_name = entry.get("recipe_name")
            if recipe_name in disliked:
                return False
                
            is_batter = entry.get("is_batter_based", False)
            category = entry.get("category", "")
            
            if is_batter:
                if idx - last_batter_idx <= 3:
                    if last_batter_category and category != last_batter_category:
                        # Switched to a different batter category within 3 days -> Invalid!
                        return False
                last_batter_idx = idx
                last_batter_category = category

        # 3: 15-day cooling-off check across full timeline
        if full_context_plan:
            # Construct a copy of the 21-day list of recipe names
            context_names = [day.get("recipe_name") if day else None for day in full_context_plan]
            # Replace target slice with the plan being validated
            for idx, entry in enumerate(plan):
                if target_offset + idx < len(context_names):
                    context_names[target_offset + idx] = entry.get("recipe_name")
                
            # Check for duplicates within any 15-day window
            last_seen = {}
            for idx, name in enumerate(context_names):
                if name:
                    if name in last_seen:
                        if idx - last_seen[name] < 15:
                            return False
                    last_seen[name] = idx
                    
        return True

    def generate_fallback_plan(self, disliked_recipes=None, full_context_plan=None, target_offset=0):
        """Generates a valid 7-day plan using a rule-based constraint solver."""
        disliked = set(disliked_recipes or [])
        allowed_recipes = [r for r in self.recipes if r.get("recipe_name") not in disliked]
        if not allowed_recipes:
            allowed_recipes = self.recipes

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        plan = []
        
        last_batter_idx = -10
        last_batter_category = None

        # Build active context copy
        context_names = []
        if full_context_plan:
            context_names = [day.get("recipe_name") if day else None for day in full_context_plan]
        else:
            context_names = [None] * 21

        for idx, day in enumerate(days):
            global_idx = target_offset + idx
            
            # Find eligible recipes
            eligible = []
            for r in allowed_recipes:
                r_name = r.get("recipe_name")
                is_batter = r.get("is_batter_based", False)
                category = r.get("category", "")
                
                # Check batter constraints
                if is_batter:
                    if idx - last_batter_idx <= 3:
                        if last_batter_category and category != last_batter_category:
                            continue
                            
                # Check 15-day cooling-off constraint
                conflict = False
                for check_idx in range(max(0, global_idx - 14), min(len(context_names), global_idx + 15)):
                    if check_idx != global_idx and check_idx < len(context_names) and context_names[check_idx] == r_name:
                        conflict = True
                        break
                if conflict:
                    continue
                    
                eligible.append(r)
                
            if not eligible:
                eligible = allowed_recipes
                
            recipe = random.choice(eligible)
            
            is_batter = recipe.get("is_batter_based", False)
            if is_batter:
                last_batter_idx = idx
                last_batter_category = recipe.get("category")
                
            if global_idx < len(context_names):
                context_names[global_idx] = recipe.get("recipe_name")
            
            plan.append({
                "day_number": idx + 1,
                "day_name": day,
                "recipe_name": recipe.get("recipe_name"),
                "category": recipe.get("category"),
                "is_batter_based": recipe.get("is_batter_based"),
                "Youtube_url": recipe.get("Youtube_url")
            })
            
        return plan

    def plan_with_llm(self, disliked_recipes=None, full_context_plan=None, target_offset=0):
        """Queries the LLM (Gemini with Ollama fallback) to generate a plan, validated programmatically."""
        disliked = disliked_recipes or []
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return self.generate_fallback_plan(disliked, full_context_plan, target_offset)

        recipes_context = []
        for r in self.recipes:
            if r.get("recipe_name") not in disliked:
                recipes_context.append({
                    "recipe_name": r.get("recipe_name"),
                    "category": r.get("category"),
                    "is_batter_based": r.get("is_batter_based"),
                    "Youtube_url": r.get("Youtube_url")
                })

        user_content = f"Generate a weekly plan. Disliked recipes list (do not use): {json.dumps(disliked)}.\nAllowed recipes:\n{json.dumps(recipes_context, indent=2)}"

        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=CONCIERGE_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2
                ),
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                raw_text = "\n".join(lines[1:-1])
            
            data = json.loads(raw_text)
            plan = data.get("weekly_plan", [])
            
            if self.validate_plan(plan, disliked, full_context_plan, target_offset) and len(plan) == 7:
                return plan
        except Exception:
            try:
                import ollama
                ollama_response = ollama.chat(
                    model='llama3.2',
                    messages=[
                        {'role': 'system', 'content': CONCIERGE_SYSTEM_PROMPT},
                        {'role': 'user', 'content': user_content}
                    ]
                )
                raw_text = ollama_response['message']['content'].strip()
                data = json.loads(raw_text)
                plan = data.get("weekly_plan", [])
                if self.validate_plan(plan, disliked, full_context_plan, target_offset) and len(plan) == 7:
                    return plan
            except Exception:
                pass

        return self.generate_fallback_plan(disliked, full_context_plan, target_offset)

    def process_chat_request(self, user_message, current_plan, disliked_recipes=None, full_context_plan=None, target_offset=0):
        """Processes the chat input to dynamically modify the plan, adhering to disliked lists and constraints."""
        disliked = disliked_recipes or []
        api_key = os.environ.get("GEMINI_API_KEY")
        
        user_content = f"Current Weekly Plan:\n{json.dumps(current_plan, indent=2)}\n\nDisliked Recipes list (never suggest these): {json.dumps(disliked)}\n\nUser Request: {user_message}"
        
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=user_content,
                    config=types.GenerateContentConfig(
                        system_instruction=CHAT_AGENT_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.3
                    ),
                )
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    raw_text = "\n".join(lines[1:-1])
                
                data = json.loads(raw_text)
                updated_plan = data.get("updated_weekly_plan", [])
                agent_resp = data.get("agent_response", "I have updated the schedule for you.")
                
                if self.validate_plan(updated_plan, disliked, full_context_plan, target_offset) and len(updated_plan) == 7:
                    return agent_resp, updated_plan
            except Exception:
                pass

        # Fallback processing if LLM is offline/errored
        msg_lower = user_message.lower()
        new_plan = [dict(day) for day in current_plan]
        disliked_set = set(disliked)
        resp_text = "I've processed your request."

        # Parse target day
        target_day_idx = None
        for d_idx, day_name in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            if day_name in msg_lower:
                target_day_idx = d_idx
                break

        # Parse category requested
        target_category = None
        for cat in ["dosa", "idli", "vada", "upma", "pongal", "rice", "appam", "paniyaram", "bonda", "roti", "sundal"]:
            if cat in msg_lower:
                target_category = cat
                break

        # Check if a specific recipe name was matched
        specific_recipe = find_best_recipe_match(user_message, self.recipes)

        # 1. Handle sick/unwell requests
        if any(w in msg_lower for w in ["sick", "unwell", "light", "stomach", "fever"]):
            light_recipe = next((r for r in self.recipes if r.get("recipe_name") not in disliked_set and r.get("recipe_name") == "Ragi Java (Ragi Porridge)"), None)
            if not light_recipe:
                light_recipe = next((r for r in self.recipes if r.get("recipe_name") not in disliked_set and r.get("recipe_name") == "Idli"), None)
            
            if light_recipe:
                new_plan[0]["recipe_name"] = light_recipe.get("recipe_name")
                new_plan[0]["category"] = light_recipe.get("category")
                new_plan[0]["is_batter_based"] = light_recipe.get("is_batter_based")
                new_plan[0]["Youtube_url"] = light_recipe.get("Youtube_url")
                resp_text = "I have updated tomorrow's breakfast to a light and comforting Ragi Java."

        # 2. Handle specific swaps or swaps on specific days
        elif target_day_idx is not None:
            recipe = None
            if specific_recipe:
                recipe = next((r for r in self.recipes if r.get("recipe_name") == specific_recipe), None)
            elif target_category:
                candidates = [r for r in self.recipes if target_category in r.get("category", "").lower() and r.get("recipe_name") not in disliked_set]
                if candidates:
                    recipe = random.choice(candidates)
            
            if recipe:
                new_plan[target_day_idx]["recipe_name"] = recipe.get("recipe_name")
                new_plan[target_day_idx]["category"] = recipe.get("category")
                new_plan[target_day_idx]["is_batter_based"] = recipe.get("is_batter_based")
                new_plan[target_day_idx]["Youtube_url"] = recipe.get("Youtube_url")
                resp_text = f"I have swapped {new_plan[target_day_idx]['day_name']}'s breakfast to {recipe.get('recipe_name')}."

        # 3. Swap disliked items selectively instead of regenerating the entire week
        for idx, entry in enumerate(new_plan):
            if entry.get("recipe_name") in disliked_set:
                alternative = None
                candidates = [r for r in self.recipes if r.get("recipe_name") not in disliked_set]
                random.shuffle(candidates)
                for r in candidates:
                    temp_plan = [dict(d) for d in new_plan]
                    temp_plan[idx]["recipe_name"] = r.get("recipe_name")
                    temp_plan[idx]["category"] = r.get("category")
                    temp_plan[idx]["is_batter_based"] = r.get("is_batter_based")
                    temp_plan[idx]["Youtube_url"] = r.get("Youtube_url")
                    
                    if self.validate_plan(temp_plan, disliked, full_context_plan, target_offset):
                        alternative = r
                        break
                
                if alternative:
                    new_plan[idx] = temp_plan[idx]
                    resp_text = f"I replaced the disliked item on {new_plan[idx]['day_name']} with {alternative.get('recipe_name')}."

        # Clean validation neighbor checks if swap caused violations
        if not self.validate_plan(new_plan, disliked, full_context_plan, target_offset):
            new_plan = self.generate_fallback_plan(disliked, full_context_plan, target_offset)
            resp_text = "I have adjusted the schedule to respect the 15-day unique recipe constraint."

        return resp_text, new_plan