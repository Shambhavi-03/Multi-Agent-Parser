# streamlit_app.py

import streamlit as st
import requests
import json
import os # <-- NEW: Import the os module

# FastAPI backend URL
# --- UPDATED: Read from environment variable, with a fallback for local development ---
FASTAPI_URL = os.getenv("FASTAPI_BACKEND_URL", "http://localhost:8000")

st.set_page_config(layout="centered", page_title="AI Multi-Format Classifier")

st.title("AI Multi-Format Classifier 🤖")
st.markdown("Upload a file (Email, JSON, PDF) or enter text to classify its format and business intent.")

# --- Initialize session state for transaction_id if it doesn't exist ---
if 'transaction_id' not in st.session_state:
    st.session_state.transaction_id = None
if 'classification_result' not in st.session_state:
    st.session_state.classification_result = None

# --- File Uploader ---
st.header("1. Upload File")
uploaded_file = st.file_uploader(
    "Choose a file",
    type=["eml", "json", "pdf", "txt"], # Allow common types, FastAPI will infer more
    help="Supported formats: .eml (Email), .json, .pdf, .txt"
)

# --- Text Input ---
st.header("2. Enter Text Directly (Alternative to File Upload)")
text_input = st.text_area(
    "Or type/paste your content here:",
    height=200,
    placeholder="e.g., Subject: Urgent Complaint...\nOr {'key': 'value'}",
    help="If a file is uploaded, text input will be ignored."
)

st.markdown("---")

classification_button = st.button("Classify Input")

if classification_button:
    # Reset session state on new classification attempt
    st.session_state.transaction_id = None
    st.session_state.classification_result = None

    if uploaded_file is None and not text_input:
        st.warning("Please upload a file or enter text before classifying.")
    else:
        st.info("Classifying input...")
        response_data = None

        # Prepare payload based on input type
        try:
            if uploaded_file:
                files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                st.write(f"Sending file: {uploaded_file.name} ({uploaded_file.type}) to **{FASTAPI_URL}/**") # Added for debug
                # --- UPDATED: POST to root path / ---
                response = requests.post(f"{FASTAPI_URL}/", files=files)
            elif text_input:
                data = {"text_input": text_input}
                st.write(f"Sending text input to **{FASTAPI_URL}/**") # Added for debug
                # --- UPDATED: POST to root path / ---
                response = requests.post(f"{FASTAPI_URL}/", data=data)

            response.raise_for_status() # Raise an exception for HTTP errors
            response_data = response.json()

            # --- Store results in session state ---
            st.session_state.transaction_id = response_data.get("transaction_id")
            st.session_state.classification_result = response_data

        except requests.exceptions.ConnectionError:
            st.error(f"Could not connect to FastAPI server at `{FASTAPI_URL}`. Please ensure the backend container (`fastapi_app`) is running and accessible.")
        except requests.exceptions.RequestException as e:
            st.error(f"Error during classification: {e}. Check the backend logs for details.")
            if 'response' in locals() and response.text:
                try:
                    st.json(response.json()) # Try to show FastAPI's error response
                except json.JSONDecodeError:
                    st.code(response.text) # Show raw text if not JSON

# --- Display results and Audit Trail after a successful classification ---
if st.session_state.classification_result:
    response_data = st.session_state.classification_result
    st.success("Classification Complete!")
    st.json(response_data) # Display raw response for debugging

    # Display key results clearly
    st.subheader("Classification Results:")
    st.write(f"**Transaction ID:** `{response_data.get('transaction_id', 'N/A')}`")
    st.write(f"**Detected Format:** `{response_data.get('format', 'N/A')}`")
    st.write(f"**Detected Intent:** `{response_data.get('intent', 'N/A')}`")
    st.write(f"**Next Step:** `{response_data.get('next_step', 'N/A')}`")

    if st.session_state.transaction_id:
        st.subheader("Audit Trail:")
        if st.button("View Full Audit Trace in Memory"):
            try:
                # The /audit/{transaction_id} endpoint path remains the same
                audit_response = requests.get(f"{FASTAPI_URL}/audit/{st.session_state.transaction_id}")
                audit_response.raise_for_status()
                st.json(audit_response.json())
            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to FastAPI server at `{FASTAPI_URL}` to fetch audit. Is it running?")
            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching audit trace: {e}. Check the backend logs.")
                if 'audit_response' in locals() and audit_response.text:
                    try:
                        st.json(audit_response.json())
                    except json.JSONDecodeError:
                        st.code(audit_response.text)