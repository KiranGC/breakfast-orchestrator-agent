# Breakfast Concierge Agent

An AI Agent designed for the Kaggle Capstone Project to plan, schedule, and orchestrate South Indian breakfast menus based on recipes and ingredients data.

## Problem Statement

•	The Problem: Managing personal nutrition involves managing trade-offs: time, dietary restrictions, and kitchen logistics. Current apps are fragmented—one for groceries, one for recipes, one for scheduling.
•	The Solution: An AI-native "Concierge Agent" that treats breakfast planning as a Constraint Satisfaction Problem.
•	Key "Wow" Factor: Unlike a static calendar, the agent optimizes for "Batter-Batching" (Idli/Dosa production) and ensures nutritional variety through a dynamic "Category Lockout" system.


## Architecture
•	Streamlit Frontend (app.py)
•	Orchestrator: A Python-based agentic framework that utilizes a system prompt to enforce logic constraints. Logic Engine Planner (src/planner.py) with its Guardrails, LLM models, fallback constraint solvers, and preposition parsers.
•	Logic Engine: Implements a "Category Cooling-Off" period where categories (e.g., Dosa/Idli) are locked out if used in the current or previous week, ensuring balanced nutrition.
•	Knowledge Base: A JSON-structured database of 100+ recipes, including metadata for "batter-based" classification and ingredient lists.
•	Tooling: Utility functions for grocery list de-duplication and automated resource retrieval (YouTube links).




```
breakfast-orchestrator-agent/
├── data/
│   └── south_indian_breakfast_recipes.json   # Parsed recipe dataset
├── src/
│   ├── planner.py                            # Agent planning & decision-making logic
│   └── utils.py                              # Utility functions (e.g., formatting, search)
├── .env.example                              # Template environment variables
├── requirements.txt                          # Python dependencies
└── README.md                                 # Project documentation
```

## Setup Instructions

1. **Clone the repository and navigate to the directory:**
   ```bash
   cd breakfast-orchestrator-agent
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy the example environment file and add your API keys:
   ```bash
   cp .env.example .env
   ```
