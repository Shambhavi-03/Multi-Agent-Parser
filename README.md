# AI Multi-Format Classifier

## 🌟 Project Overview

The AI Multi-Format Classifier is a robust application designed to automatically detect the format (e.g., Email, JSON, PDF) and classify the business intent of various inputs (files or text). It leverages a FastAPI backend for core logic and agent orchestration, a Streamlit frontend for a user-friendly interface, and Redis for maintaining an audit trail of transactions. The entire system is containerized using Docker Compose for easy setup and deployment.

### Key Features:

* **Multi-Format Input:** Accepts `.eml`, `.json`, `.pdf`, and plain text inputs.
* **AI-Powered Classification:** Uses a Large Language Model (LLM) (e.g., Gemini) to determine input format and business intent.
* **Agent-Based Processing:** Routes classified inputs to specialized agents (Email, JSON, PDF) for further extraction and processing.
* **Action Routing:** Triggers simulated external actions (e.g., CRM escalation, risk alerts) based on classification and extracted data.
* **Audit Trail:** Maintains a comprehensive audit log of each transaction in Redis, accessible via a dedicated API endpoint.
* **User-Friendly Interface:** A Streamlit web application provides a simple way to upload files or enter text and view results.
* **Containerized Deployment:** Uses Docker Compose for isolated and reproducible development and deployment environments.

## 📸 Screenshots

## 🚀 Getting Started

Follow these steps to get the **AI Multi-Format Classifier** up and running on your local machine.

---

### ✅ Prerequisites

Ensure the following tools are installed:

- **Git**: Used to clone the repository  
  👉 [Download Git](https://git-scm.com/downloads)

- **Docker**: Required to run containerized services  
  👉 [Install Docker Desktop (Windows/macOS)](https://www.docker.com/products/docker-desktop)  
  👉 [Install Docker Engine (Linux)](https://docs.docker.com/engine/install/)  
  👉 [Install Docker Compose (Linux)](https://docs.docker.com/compose/install/)

- **Gemini API Key**: Required to access the LLM from Google.

#### 🔑 How to Get Your Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app)
2. Sign in with your Google account.
3. Navigate to the **API Keys** section.
4. Click **Create API Key**.
5. Copy the generated API key — you’ll need this in the next step.

---

### ⚙️ Setup Instructions

#### 1. Clone the Repository

Open your terminal and run:

```bash
git clone https://github.com/Shambhavi-03/Multi-Agent-Parser.git
cd Multi-Agent-Parser
```

#### 2.  Create a `.env` File:

This project uses environment variables for sensitive information, particularly your LLM API key.
Add your Gemini API Key:

   On Linux/macOS (Bash/Zsh):
   ```bash
      export GEMINI_API_KEY="your_actual_gemini_api_key"
   ```
   On Windows (Command Prompt):
   ```cmd
      set GEMINI_API_KEY="your_actual_gemini_api_key"
   ```
   On Windows (PowerShell):
   ```powershell
      $env:GEMINI_API_KEY="your_actual_gemini_api_key"
   ```
   Or you can create a `.env` file in the root of the project (same directory as `docker-compose.yml`) and add:

   ```ini
      GEMINI_API_KEY="your_actual_gemini_api_key"
   ```
      
Replace `"YOUR_GEMINI_API_KEY_HERE"` with your actual key obtained from Google AI Studio.

#### 3. Build and Run with Docker Compose

From the project root, run the following command:

```bash
    docker-compose up --build -d
```

### 🌐 Access the Applications

Once the containers are running (this might take 1--2 minutes initially):

-   **Streamlit Frontend (User Interface)**\
    👉 Open <http://localhost:8501> in your browser.

-   **FastAPI Documentation (Swagger UI)**\
    👉 Open <http://localhost:8000/docs>

-   **FastAPI Root Endpoint (POST Classifier API)**\
    You can POST input directly to: `http://localhost:8000/`

You can test this via the Streamlit UI, the Swagger UI (`/docs`), or a tool like `curl` or Postman.
Example `curl` command for text input:
   ```bash
        curl -X POST "http://localhost:8000/" \
             -H "Content-Type: application/x-www-form-urlencoded" \
             -d "text_input=This is a customer inquiry about a refund."
   ```

### 🛑 Stopping the Applications

To stop and remove the running Docker containers (but keep the images and Redis data volume):

```bash
docker-compose down
```
To stop and remove containers, associated Docker images, and all volumes (for a completely clean slate, useful for troubleshooting or starting fresh):

```bash
docker-compose down --volumes --rmi all
```

## 🤝 Contributing

We welcome contributions to this project! If you have suggestions for improvements, new features, or find any bugs, please feel free to:

*   Open an issue on GitHub.
    
*   Submit a pull request.
    
## ▶️ Watch the Demo Video

See the AI Multi-Format Classifier in action! [Watch the Full Demo Here]([LINK_TO_YOUR_YOUTUBE_OR_VIMEO_VIDEO](https://drive.google.com/file/d/1hdE_SBvMwVbwPJs5pwRMjjrFW1ohay5S/view?usp=sharing))

## 📄 License

This project is licensed under the MIT License. You can find the full license text in the LICENSE file in the repository.
