import streamlit as st
import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

# Ensure the root/src directories are in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.planner import BreakfastPlanner
from src.utils import aggregate_grocery_list, find_best_recipe_match

# Load environment variables
load_dotenv()

# App configuration
st.set_page_config(
    page_title="Breakfast Concierge Agent",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed"  # Collapse sidebar by default
)

# Custom premium styling (Calendar style, uniform squares, gear alignment)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at top right, #1a1a2e, #0e0e12 80%);
        color: #f1f1f5;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #a8c0ff 0%, #3f2b96 100%);
        color: white;
        border: none;
        padding: 8px 20px;
        border-radius: 12px;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(63, 43, 150, 0.3);
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(63, 43, 150, 0.5);
    }
    
    /* Calendar Card styling - uniform square */
    .calendar-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 4px solid #3f2b96; /* Accent calendar line */
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 10px;
        height: 220px;
        backdrop-filter: blur(20px);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: all 0.3s ease;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }
    
    .calendar-card:hover {
        transform: translateY(-3px);
        background: rgba(255, 255, 255, 0.04);
        border-color: rgba(255, 255, 255, 0.15);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
    }
    
    /* Highlighted selected calendar card */
    .selected-card {
        border: 2px solid #a8c0ff !important;
        border-top: 4px solid #a8c0ff !important;
        box-shadow: 0 0 20px rgba(168, 192, 255, 0.4) !important;
        background: rgba(255, 255, 255, 0.06) !important;
    }

    .calendar-card h3 {
        margin: 0;
        font-size: 1.15rem;
        font-weight: 700;
        color: #f1f1f5;
    }

    .calendar-date {
        font-size: 0.85rem;
        color: #a8c0ff;
        font-weight: 500;
        margin-bottom: 8px;
    }
    
    /* Pastel Badge Styles */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
        width: fit-content;
    }

    .badge-dosa {
        background-color: rgba(255, 179, 102, 0.12);
        color: #ffb366;
        border: 1px solid rgba(255, 179, 102, 0.2);
    }

    .badge-idli {
        background-color: rgba(255, 230, 153, 0.12);
        color: #ffe699;
        border: 1px solid rgba(255, 230, 153, 0.2);
    }

    .badge-vada {
        background-color: rgba(179, 255, 179, 0.12);
        color: #b3ffb3;
        border: 1px solid rgba(179, 255, 179, 0.2);
    }

    .badge-upma {
        background-color: rgba(153, 204, 255, 0.12);
        color: #99ccff;
        border: 1px solid rgba(153, 204, 255, 0.2);
    }

    .badge-appam {
        background-color: rgba(255, 153, 204, 0.12);
        color: #ff99cc;
        border: 1px solid rgba(255, 153, 204, 0.2);
    }

    .badge-rice {
        background-color: rgba(204, 153, 255, 0.12);
        color: #cc99ff;
        border: 1px solid rgba(204, 153, 255, 0.2);
    }

    .badge-bonda {
        background-color: rgba(255, 204, 153, 0.12);
        color: #ffcc99;
        border: 1px solid rgba(255, 204, 153, 0.2);
    }

    .badge-others {
        background-color: rgba(200, 200, 200, 0.08);
        color: #d0d0d0;
        border: 1px solid rgba(200, 200, 200, 0.15);
    }

    .chat-panel {
        background: rgba(255, 255, 255, 0.01);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 24px;
        padding: 20px;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.15);
    }
</style>
""", unsafe_allow_html=True)

# Helper function to initialize session state data
def init_session():
    planner = BreakfastPlanner()
    
    if "prior_week" not in st.session_state:
        st.session_state.prior_week = [
            {"day_number": 1, "day_name": "Monday", "recipe_name": "Masala Dosa", "category": "Dosa", "is_batter_based": True, "Youtube_url": "https://www.youtube.com/results?search_query=Masala%20Dosa%20recipe"},
            {"day_number": 2, "day_name": "Tuesday", "recipe_name": "Rava Upma", "category": "Upma", "is_batter_based": False, "Youtube_url": "https://www.youtube.com/results?search_query=Rava%20Upma%20recipe"},
            {"day_number": 3, "day_name": "Wednesday", "recipe_name": "Idli", "category": "Idli", "is_batter_based": True, "Youtube_url": "https://www.youtube.com/results?search_query=Idli%20recipe"},
            {"day_number": 4, "day_name": "Thursday", "recipe_name": "Medu Vada", "category": "Vada", "is_batter_based": False, "Youtube_url": "https://www.youtube.com/results?search_query=Medu%20Vada%20recipe"},
            {"day_number": 5, "day_name": "Friday", "recipe_name": "Lemon Rice", "category": "Rice", "is_batter_based": False, "Youtube_url": "https://www.youtube.com/results?search_query=Lemon%20Rice%20recipe"},
            {"day_number": 6, "day_name": "Saturday", "recipe_name": "Appam", "category": "Appam", "is_batter_based": True, "Youtube_url": "https://www.youtube.com/results?search_query=Appam%20recipe"},
            {"day_number": 7, "day_name": "Sunday", "recipe_name": "Sabudana Khichdi", "category": "Khichdi", "is_batter_based": False, "Youtube_url": "https://www.youtube.com/results?search_query=Sabudana%20Khichdi%20recipe"}
        ]
        
    if "current_week" not in st.session_state:
        st.session_state.current_week = planner.generate_fallback_plan()
        
    if "next_week" not in st.session_state:
        st.session_state.next_week = planner.generate_fallback_plan()

    if "current_week_idx" not in st.session_state:
        st.session_state.current_week_idx = 1  # 0: Prior, 1: Current, 2: Next

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Namaskara! I am your Breakfast Concierge Chef. Let me know if you dislike a recipe (e.g. 'I don't like Upma') and I will exclude it from future planning."}
        ]

    if "disliked_recipes" not in st.session_state:
        st.session_state.disliked_recipes = []

    if "selected_day_idx" not in st.session_state:
        st.session_state.selected_day_idx = None

# Initialize Data
init_session()

# Top Row Header & Settings Gear
col_header, col_nav, col_gear = st.columns([1.8, 1, 0.4], gap="small")

with col_header:
    st.title("🍳 Breakfast Concierge")

with col_nav:
    week_options = ["Prior Week (History)", "Current Week (Active)", "Next Week (Planned)"]
    selected_week = st.selectbox("📅 View Week", options=week_options, index=st.session_state.current_week_idx, label_visibility="collapsed")
    
    # Reset selected day if the week selection changes
    if st.session_state.current_week_idx != week_options.index(selected_week):
        st.session_state.current_week_idx = week_options.index(selected_week)
        st.session_state.selected_day_idx = None

with col_gear:
    # Gear popover replaces sidebar
    with st.popover("⚙️", help="Configure Keys & Disliked Recipes"):
        st.markdown("### Settings")
        gemini_key = st.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key
            
        st.markdown("---")
        st.markdown("#### Disliked Recipes (Excluded)")
        if st.session_state.disliked_recipes:
            for item in st.session_state.disliked_recipes:
                col_i, col_d = st.columns([4, 1])
                col_i.write(f"- {item}")
                if col_d.button("🗑️", key=f"del_{item}"):
                    st.session_state.disliked_recipes.remove(item)
                    st.session_state.selected_day_idx = None
                    st.rerun()
            if st.button("Clear All"):
                st.session_state.disliked_recipes = []
                st.session_state.selected_day_idx = None
                st.rerun()
        else:
            st.info("No recipes currently excluded.")

# Calculate dates dynamically based on selected week
today = date.today()
if st.session_state.current_week_idx == 0:
    start_date = today - timedelta(days=7)
elif st.session_state.current_week_idx == 1:
    start_date = today
else:
    start_date = today + timedelta(days=7)

# Active plan reference
if st.session_state.current_week_idx == 0:
    active_plan = st.session_state.prior_week
elif st.session_state.current_week_idx == 1:
    active_plan = st.session_state.current_week
else:
    active_plan = st.session_state.next_week

# Main layout splitting
left_col, right_col = st.columns([2.2, 0.8])

with left_col:
    # Plan generation options
    if st.session_state.current_week_idx > 0:
        col_gen1, col_gen2 = st.columns([1, 4])
        with col_gen1:
            if st.button("🔄 Refresh Plan"):
                with st.spinner("Agent Chef is cooking up your schedule..."):
                    try:
                        planner = BreakfastPlanner()
                        full_context = (
                            st.session_state.prior_week + 
                            st.session_state.current_week + 
                            st.session_state.next_week
                        )
                        offset = 7 if st.session_state.current_week_idx == 1 else 14
                        
                        new_plan = planner.plan_with_llm(
                            st.session_state.disliked_recipes,
                            full_context,
                            offset
                        )
                        if st.session_state.current_week_idx == 1:
                            st.session_state.current_week = new_plan
                        else:
                            st.session_state.next_week = new_plan
                        st.session_state.selected_day_idx = None  # Reset selection
                        st.success("Successfully generated schedule!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error calling planner engine: {e}")

    # Render 7-day layout in uniform square cards (Row 1: 4 columns, Row 2: 3 columns)
    row1_cols = st.columns(4)
    row2_cols = st.columns(3)
    
    for idx, day_info in enumerate(active_plan):
        day_name = day_info.get("day_name", f"Day {idx+1}")
        recipe_name = day_info.get("recipe_name", "N/A")
        category = day_info.get("category", "N/A")
        is_batter = day_info.get("is_batter_based", False)
        yt_url = day_info.get("Youtube_url", "#")
        
        # Calculate Date
        day_date = (start_date + timedelta(days=idx)).strftime("%b %d")
        
        # Pick the column based on row structure
        if idx < 4:
            col = row1_cols[idx]
        else:
            col = row2_cols[idx - 4]
            
        # Determine badge CSS class
        badge_style = "badge-others"
        cat_lower = category.lower()
        if "dosa" in cat_lower:
            badge_style = "badge-dosa"
        elif "idli" in cat_lower:
            badge_style = "badge-idli"
        elif "vada" in cat_lower:
            badge_style = "badge-vada"
        elif "upma" in cat_lower:
            badge_style = "badge-upma"
        elif "appam" in cat_lower or "paniyaram" in cat_lower:
            badge_style = "badge-appam"
        elif "rice" in cat_lower:
            badge_style = "badge-rice"
        elif "bonda" in cat_lower:
            badge_style = "badge-bonda"
        
        # Check selection status
        is_selected = (st.session_state.selected_day_idx == idx)
        card_class = "calendar-card selected-card" if is_selected else "calendar-card"
        
        col.markdown(f"""
        <div class="{card_class}">
            <div>
                <div class="calendar-date">{day_date} • {day_name}</div>
                <span class="badge {badge_style}">{category}</span>
                <p style="font-size: 1.1rem; font-weight: 600; margin: 6px 0; line-height: 1.3;">{recipe_name}</p>
            </div>
            <a href="{yt_url}" target="_blank" style="text-decoration: none; color: #a8c0ff; font-weight: 500; font-size: 0.85rem;">📺 View Recipe</a>
        </div>
        """, unsafe_allow_html=True)
        
        # Selection button inside the card layout column
        if col.button("📋 Select Day" if not is_selected else "✅ Selected", key=f"select_{idx}", use_container_width=True):
            if is_selected:
                st.session_state.selected_day_idx = None  # Deselect on second click
            else:
                st.session_state.selected_day_idx = idx
            st.rerun()

    # Generate grocery checklist section
    st.write("---")
    
    # Configure dynamic grocery list focus
    grocery_plan = active_plan
    grocery_title = "Consolidated ingredients list for the selected week:"
    
    if st.session_state.selected_day_idx is not None:
        selected_day = active_plan[st.session_state.selected_day_idx]
        grocery_plan = [selected_day]
        grocery_title = f"Ingredients needed for {selected_day.get('day_name')} ({selected_day.get('recipe_name')}):"
        
        col_list_header, col_list_reset = st.columns([3, 1])
        with col_list_header:
            st.subheader("🛒 Interactive Grocery List (Single Day)")
        with col_list_reset:
            if st.button("📋 Show Whole Week List", use_container_width=True):
                st.session_state.selected_day_idx = None
                st.rerun()
    else:
        st.subheader("🛒 Interactive Grocery List")
        
    st.write(grocery_title)

    try:
        grocery_list = aggregate_grocery_list(grocery_plan)
        if grocery_list:
            col_list1, col_list2 = st.columns(2)
            half = len(grocery_list) // 2 + 1
            
            with col_list1:
                for item in grocery_list[:half]:
                    st.checkbox(item, key=f"grocery_{selected_week}_{item}")
            with col_list2:
                for item in grocery_list[half:]:
                    st.checkbox(item, key=f"grocery_{selected_week}_{item}")
        else:
            st.info("No ingredients found for the current plan.")
    except Exception as e:
        st.error(f"An error occurred while compiling the grocery list: {e}")

# Right Column: Chef Concierge Chat
with right_col:
    st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
    st.subheader("💬 Chef Concierge")
    st.caption("Customize your menu here. Ask to replace recipes or tag dislikes.")
    
    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Input field
    if user_prompt := st.chat_input("Suggest a change..."):
        # Reset day selection on new chat request to focus back to week view
        st.session_state.selected_day_idx = None
        
        # Programmatic parsing for dislikes/exclusions
        msg_lower = user_prompt.lower()
        disliked_detected = []
        
        planner = BreakfastPlanner()
        # Find closest match for dislikes in database using sequence matching (typo tolerance)
        if any(w in msg_lower for w in ["don't like", "dislike", "remove", "exclude", "never show"]):
            matched_recipe = find_best_recipe_match(user_prompt, planner.recipes)
            if matched_recipe:
                disliked_detected.append(matched_recipe)
                    
        # Add to session state
        for d in disliked_detected:
            if d not in st.session_state.disliked_recipes:
                st.session_state.disliked_recipes.append(d)

        # Append user message
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Chef is thinking..."):
                try:
                    # Feed the current active plan and disliked list to the agent
                    full_context = (
                        st.session_state.prior_week + 
                        st.session_state.current_week + 
                        st.session_state.next_week
                    )
                    offset = 7 if st.session_state.current_week_idx == 1 else 14
                    
                    agent_reply, updated_plan = planner.process_chat_request(
                        user_prompt, active_plan, st.session_state.disliked_recipes, full_context, offset
                    )
                    
                    if disliked_detected:
                        agent_reply += f"\n\n*(Added {', '.join(disliked_detected)} to your disliked list. I will exclude them going forward.)*"
                    
                    # Update session state plan based on the active index
                    if st.session_state.current_week_idx == 1:
                        st.session_state.current_week = updated_plan
                    elif st.session_state.current_week_idx == 2:
                        st.session_state.next_week = updated_plan
                    
                    st.write(agent_reply)
                    st.session_state.messages.append({"role": "assistant", "content": agent_reply})
                    st.rerun()
                except Exception as e:
                    err_msg = f"Sorry, I ran into an error adjusting your recipes: {e}"
                    st.write(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)