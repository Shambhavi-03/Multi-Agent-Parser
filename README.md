uvicorn flowbit.main_app:app --reload --port 8000

streamlit run streamlit_app.py

.
├── your_project_name/
│   ├── __init__.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── classifier_agent.py   # Code for the Classifier Agent logic
│   │   ├── email_agent.py        # Code for the Email Agent logic
│   │   ├── json_agent.py         # Code for the JSON Agent logic
│   │   └── pdf_agent.py          # Code for the PDF Agent logic
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── shared_memory.py      # Redis client, read/write functions
│   │   ├── llm_client.py         # Ollama/Gemini client, prompt handling, classify_with_llm/ollama
│   │   └── action_router.py      # Logic for routing to simulated CRM/Risk Alert
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py            # Pydantic models, JSON schemas for validation
│   │
│   └── main_app.py               # FastAPI application, main entry point, routes
│
├── streamlit_app.py              # Your Streamlit UI application
├── requirements.txt              # All Python dependencies
├── .env                          # Environment variables (API keys, etc.)
├── README.md                     # Project description and setup instructions
└── docker-compose.yml            # (Optional) For containerizing FastAPI, Redis, Ollama