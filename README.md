## Docker Setup (Recommended for Easy Deployment)

This project provides Dockerfiles and a `docker-compose.yml` to containerize the FastAPI backend, Streamlit frontend, and a Redis database. This is the easiest way to get the entire application running.

### Prerequisites

* **Docker Desktop:** Ensure Docker Desktop (or Docker Engine on Linux) is installed and running.
* **Google Gemini API Key:** You still need to obtain a `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/).

### Steps

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Shambhavi-03/Multi-Agent-Parser.git](https://github.com/Shambhavi-03/Multi-Agent-Parser.git)
    cd Multi-Agent-Parser
    ```

2.  **Create your `.env` file:**
    Create a file named `.env` in the root directory of the project (at the same level as `docker-compose.yml`).
    Add your Gemini API Key and optionally Redis connection details:
    ```
    GEMINI_API_KEY="YOUR_ACTUAL_GEMINI_API_KEY_HERE"
    # Optional: If you need to specify different Redis settings for Docker Compose
    # REDIS_HOST=redis
    # REDIS_PORT=6379
    # REDIS_DB=0
    ```
    **DO NOT commit your `.env` file to Git!** Ensure `.env` is in your `.gitignore`.

3.  **Build and Run with Docker Compose:**
    From the project's root directory, run:
    ```bash
    docker-compose up --build -d
    ```
    * `--build`: This forces Docker Compose to rebuild the images, ensuring any code changes are picked up.
    * `-d`: This runs the containers in detached mode (in the background).

4.  **Access the Application:**
    Once the containers are up:
    * **FastAPI Backend (API Docs):** Access your API documentation at `http://localhost:8000/docs`
    * **Streamlit Frontend (UI):** Access the user interface at `http://localhost:8501`

### Useful Docker Compose Commands

* **Stop containers:** `docker-compose down`
* **Stop and remove containers, networks, and volumes:** `docker-compose down --volumes` (use this if you want to clear Redis data)
* **View logs:** `docker-compose logs -f` (use `-f` to follow logs live, add service name like `fastapi_app` to see specific service logs)
* **List running containers:** `docker-compose ps`

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