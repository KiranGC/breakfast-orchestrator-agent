import json
import os
import random
from datetime import date, timedelta
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

    def validate_plan(self, plan, disliked_recipes=None, full_context_plan=None, target_offset=0, allowed_repeats=None):
        """
        Validates the refined constraints:
        1. No recipe in disliked_recipes is included.
        2. Refined batter category cooling-off constraint:
           If Day N uses a batter category (e.g. Dosa), Day N+1, N+2, and N+3 cannot use a DIFFERENT batter category.
           Repeats of the same batter category (Dosa -> Dosa) are allowed.
        3. 15-day recipe cooling-off constraint:
           The same recipe cannot appear within a 15-day window in the full 21-day timeline,
           except when explicitly allowed in allowed_repeats.
           Only checks for duplicates involving the target week slice.
        """
        disliked = set(disliked_recipes or [])
        repeats_set = set(allowed_repeats or [])
        
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

        # 3: 15-day cooling-off check across full timeline (scoped to plan slice)
        if full_context_plan:
            context_names = [day.get("recipe_name") if day else None for day in full_context_plan]
            # Replace target slice with the plan being validated
            for idx, entry in enumerate(plan):
                if target_offset + idx < len(context_names):
                    context_names[target_offset + idx] = entry.get("recipe_name")
                
            # Verify conflicts specifically relative to the plan indices
            for idx in range(len(plan)):
                global_idx = target_offset + idx
                name = context_names[global_idx]
                if name and name not in repeats_set:
                    for other_idx, other_name in enumerate(context_names):
                        if other_idx != global_idx and other_name == name:
                            if abs(global_idx - other_idx) < 15:
                                return False
                    
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

    def process_chat_request(self, user_message, current_plan, disliked_recipes=None, full_context_plan=None, target_offset=0, pending_swap=None):
        """Processes the chat input to dynamically modify the plan, adhering to disliked lists and constraints."""
        disliked = disliked_recipes or []
        api_key = os.environ.get("GEMINI_API_KEY")
        
        # Check if gemini is active and we are not handling a simple confirmation flow
        if api_key and not pending_swap:
            user_content = f"Current Weekly Plan:\n{json.dumps(current_plan, indent=2)}\n\nDisliked Recipes list (never suggest these): {json.dumps(disliked)}\n\nUser Request: {user_message}"
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
                    return agent_resp, updated_plan, full_context_plan, None
            except Exception:
                pass

        # Fallback processing if LLM is offline/errored
        msg_lower = user_message.lower()
        new_plan = [dict(day) for day in current_plan]
        disliked_set = set(disliked)
        resp_text = "I've processed your request."

        # Check for simple confirmation flow first
        if pending_swap and any(w in msg_lower for w in ["yes", "ok", "okay", "sure", "confirm", "go ahead"]):
            recipe_name = pending_swap.get("recipe_name")
            target_day_idx = pending_swap.get("day_idx")
            recipe = next((r for r in self.recipes if r.get("recipe_name") == recipe_name), None)
            
            if recipe and target_day_idx is not None:
                new_plan[target_day_idx]["recipe_name"] = recipe.get("recipe_name")
                new_plan[target_day_idx]["category"] = recipe.get("category")
                new_plan[target_day_idx]["is_batter_based"] = recipe.get("is_batter_based")
                new_plan[target_day_idx]["Youtube_url"] = recipe.get("Youtube_url")
                resp_text = f"Confirmed! I have added {recipe.get('recipe_name')} for {new_plan[target_day_idx]['day_name']}."
                
                # Update context timeline directly
                if full_context_plan:
                    for idx, entry in enumerate(new_plan):
                        if target_offset + idx < len(full_context_plan):
                            full_context_plan[target_offset + idx] = entry
                            
                    # Clean future upcoming duplicate matches
                    temp_context = [day.get("recipe_name") if day else None for day in full_context_plan]
                    for check_idx in range(target_offset + 7, len(temp_context)):
                        if temp_context[check_idx] == recipe.get("recipe_name"):
                            alternative = None
                            candidates = [r for r in self.recipes if r.get("recipe_name") not in disliked_set and r.get("recipe_name") != recipe.get("recipe_name")]
                            random.shuffle(candidates)
                            for r in candidates:
                                temp_week_idx = check_idx // 7
                                temp_offset = temp_week_idx * 7
                                temp_plan = [dict(d) for d in full_context_plan[temp_offset:temp_offset+7]]
                                temp_plan[check_idx % 7]["recipe_name"] = r.get("recipe_name")
                                temp_plan[check_idx % 7]["category"] = r.get("category")
                                temp_plan[check_idx % 7]["is_batter_based"] = r.get("is_batter_based")
                                temp_plan[check_idx % 7]["Youtube_url"] = r.get("Youtube_url")
                                
                                if self.validate_plan(temp_plan, disliked_set, full_context_plan, temp_offset, allowed_repeats={recipe.get("recipe_name")}):
                                    alternative = r
                                    break
                            
                            if alternative:
                                full_context_plan[check_idx]["recipe_name"] = alternative.get("recipe_name")
                                full_context_plan[check_idx]["category"] = alternative.get("category")
                                full_context_plan[check_idx]["is_batter_based"] = alternative.get("is_batter_based")
                                full_context_plan[check_idx]["Youtube_url"] = alternative.get("Youtube_url")
                                resp_text += f" Also revised upcoming week's plan on {full_context_plan[check_idx]['day_name']} to replace duplicate {recipe.get('recipe_name')}."
            
            return resp_text, new_plan, full_context_plan, None

        # Parse target day
        target_day_idx = None
        for d_idx, day_name in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            if day_name in msg_lower:
                target_day_idx = d_idx
                break

        # Check if user requested a "replace <recipe>" or "replace <recipe1> with <recipe2>"
        replace_mode = False
        if "replace" in msg_lower:
            # Look for which recipe in the current week's plan is mentioned in the user message
            for idx, entry in enumerate(new_plan):
                rec_name = entry.get("recipe_name", "")
                if rec_name.lower() in msg_lower:
                    target_day_idx = idx
                    replace_mode = True
                    break
            
            # If we matched a recipe from the current week's plan, check if we have an alternate replacement recipe
            if replace_mode:
                if "with" in msg_lower:
                    parts = msg_lower.split("with", 1)
                    after_with = parts[1].strip()
                    specific_recipe = find_best_recipe_match(after_with, self.recipes)
                else:
                    specific_recipe = None

        # Parse category requested
        target_category = None
        category_search_text = msg_lower
        if replace_mode:
            if "with" in msg_lower:
                parts = msg_lower.split("with", 1)
                category_search_text = parts[1]
            else:
                category_search_text = ""

        for cat in ["dosa", "idli", "vada", "upma", "pongal", "rice", "appam", "paniyaram", "bonda", "roti", "sundal"]:
            if cat in category_search_text:
                target_category = cat
                break

        # Check if a specific recipe name was matched (only if not already override matched in replace mode)
        if not replace_mode:
            specific_recipe = find_best_recipe_match(user_message, self.recipes)
        allowed_repeats = set()

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
            
            # Fallback if no specific recipe or category matched (e.g. they wrote "replace Appam")
            if not recipe:
                old_name = new_plan[target_day_idx].get("recipe_name")
                candidates = [r for r in self.recipes if r.get("recipe_name") not in disliked_set and r.get("recipe_name") != old_name]
                random.shuffle(candidates)
                for r in candidates:
                    temp_plan = [dict(d) for d in new_plan]
                    temp_plan[target_day_idx]["recipe_name"] = r.get("recipe_name")
                    temp_plan[target_day_idx]["category"] = r.get("category")
                    temp_plan[target_day_idx]["is_batter_based"] = r.get("is_batter_based")
                    temp_plan[target_day_idx]["Youtube_url"] = r.get("Youtube_url")
                    
                    if self.validate_plan(temp_plan, disliked_set, full_context_plan, target_offset):
                        recipe = r
                        break
            
            if recipe:
                # Check if it was prepared in previous week (global index 0 to 6)
                is_in_prev = False
                prev_day_idx = None
                if full_context_plan:
                    for p_idx in range(min(7, len(full_context_plan))):
                        if full_context_plan[p_idx] and full_context_plan[p_idx].get("recipe_name") == recipe.get("recipe_name"):
                            is_in_prev = True
                            prev_day_idx = p_idx
                            break
                            
                if is_in_prev:
                    # Calculate exact date of index prev_day_idx
                    today = date.today()
                    prior_week_monday = today - timedelta(days=today.weekday() + 7)
                    prev_date = prior_week_monday + timedelta(days=prev_day_idx)
                    prev_date_str = prev_date.strftime("%b %d")
                    prev_day_name = full_context_plan[prev_day_idx].get("day_name", "")
                    
                    # Request confirmation instead of applying swap directly
                    next_pending = {"recipe_name": recipe.get("recipe_name"), "day_idx": target_day_idx}
                    resp_text = f"{recipe.get('recipe_name')} was prepared on {prev_date_str} ({prev_day_name}). Is it okay to repeat it?"
                    return resp_text, current_plan, full_context_plan, next_pending
                
                # Otherwise perform the swap immediately
                old_recipe_name = new_plan[target_day_idx]["recipe_name"]
                new_plan[target_day_idx]["recipe_name"] = recipe.get("recipe_name")
                new_plan[target_day_idx]["category"] = recipe.get("category")
                new_plan[target_day_idx]["is_batter_based"] = recipe.get("is_batter_based")
                new_plan[target_day_idx]["Youtube_url"] = recipe.get("Youtube_url")
                
                if replace_mode:
                    resp_text = f"I have replaced {old_recipe_name} on {new_plan[target_day_idx]['day_name']} with {recipe.get('recipe_name')}."
                else:
                    resp_text = f"I have swapped {new_plan[target_day_idx]['day_name']}'s breakfast to {recipe.get('recipe_name')}."
                
                # Register override for explicit user selection repeat
                allowed_repeats.add(recipe.get("recipe_name"))
                
                # Update full_context_plan slice immediately
                if full_context_plan:
                    for idx, entry in enumerate(new_plan):
                        if target_offset + idx < len(full_context_plan):
                            full_context_plan[target_offset + idx] = entry
                
                # Check for repeats in upcoming week and replace them
                if full_context_plan:
                    temp_context = [day.get("recipe_name") if day else None for day in full_context_plan]
                    for check_idx in range(target_offset + 7, len(temp_context)):
                        if temp_context[check_idx] == recipe.get("recipe_name"):
                            alternative = None
                            candidates = [r for r in self.recipes if r.get("recipe_name") not in disliked_set and r.get("recipe_name") != recipe.get("recipe_name")]
                            random.shuffle(candidates)
                            for r in candidates:
                                temp_week_idx = check_idx // 7
                                temp_offset = temp_week_idx * 7
                                temp_plan = [dict(d) for d in full_context_plan[temp_offset:temp_offset+7]]
                                temp_plan[check_idx % 7]["recipe_name"] = r.get("recipe_name")
                                temp_plan[check_idx % 7]["category"] = r.get("category")
                                temp_plan[check_idx % 7]["is_batter_based"] = r.get("is_batter_based")
                                temp_plan[check_idx % 7]["Youtube_url"] = r.get("Youtube_url")
                                
                                if self.validate_plan(temp_plan, disliked_set, full_context_plan, temp_offset, allowed_repeats={recipe.get("recipe_name")}):
                                    alternative = r
                                    break
                            
                            if alternative:
                                full_context_plan[check_idx]["recipe_name"] = alternative.get("recipe_name")
                                full_context_plan[check_idx]["category"] = alternative.get("category")
                                full_context_plan[check_idx]["is_batter_based"] = alternative.get("is_batter_based")
                                full_context_plan[check_idx]["Youtube_url"] = alternative.get("Youtube_url")
                                resp_text += f" Also revised upcoming week's plan on {full_context_plan[check_idx]['day_name']} to replace duplicate {recipe.get('recipe_name')}."

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
                    
                    if self.validate_plan(temp_plan, disliked, full_context_plan, target_offset, allowed_repeats=allowed_repeats):
                        alternative = r
                        break
                
                if alternative:
                    new_plan[idx] = temp_plan[idx]
                    resp_text = f"I replaced the disliked item on {new_plan[idx]['day_name']} with {alternative.get('recipe_name')}."

        # Clean validation neighbor checks if swap caused violations
        if not self.validate_plan(new_plan, disliked, full_context_plan, target_offset, allowed_repeats=allowed_repeats):
            new_plan = self.generate_fallback_plan(disliked, full_context_plan, target_offset)
            resp_text = "I have adjusted the schedule to respect the 15-day unique recipe constraint."

        # Synchronize context slice for this week
        if full_context_plan:
            for idx in range(7):
                if target_offset + idx < len(full_context_plan):
                    full_context_plan[target_offset + idx] = new_plan[idx]

        return resp_text, new_plan, full_context_plan, None