# your_project_name/main_app.py

from dotenv import load_dotenv
load_dotenv() # This loads variables from .env

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from typing import Optional
from datetime import datetime
import json
import uuid

# Import core utilities and agents
from .core import shared_memory
from .core import llm_client 
from .core import action_router
from .agents import classifier_agent
from .agents import email_agent
from .agents import json_agent
from .agents import pdf_agent # UNCOMMENT THIS LINE

app = FastAPI()

# --- Shared Memory Audit Endpoint ---
@app.get("/audit/{transaction_id}")
async def audit_trace(transaction_id: str):
    """
    Retrieves the full audit trace for a given transaction ID from shared memory.
    """
    trace = shared_memory.get_transaction_data(transaction_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Transaction ID not found")
    return trace

# --- Classifier Agent Endpoint ---
@app.post("/classify/")
async def classify_input(
    file: Optional[UploadFile] = File(None),
    text_input: Optional[str] = Form(None)
):
    """
    Receives input (file or text), detects format and business intent using LLM,
    stores metadata in shared memory, and triggers the next appropriate agent.
    """
    transaction_id = str(uuid.uuid4())
    current_timestamp = datetime.now().isoformat()
    
    # Initialize transaction data in shared memory early to ensure trace starts
    shared_memory.set_transaction_data(transaction_id, {
        "transaction_id": transaction_id,
        "timestamp": current_timestamp,
        "raw_input_type": "file" if file else "text",
        "initial_input_preview": (file.filename if file else text_input[:100]) if (file or text_input) else "No input provided",
        "agent_decision_trace": [] # Initialize trace list
    })

    try:
        # Perform initial classification using the Classifier Agent logic
        classification_result = await classifier_agent.classify_input_data(
            transaction_id,
            current_timestamp,
            file,
            text_input
        )

        detected_format = classification_result.get("format")
        detected_intent = classification_result.get("intent")

        # --- Routing Logic ---
        print(f"Classifier Agent: Transaction {transaction_id} - Format: {detected_format}, Intent: {detected_intent}")
        print(f"Routing to {detected_format} Agent...")

        next_step_message = f"Processing by {detected_format} Agent..."
        
        if detected_format == "Email":
            await email_agent.process_email(transaction_id)
        elif detected_format == "JSON":
            await json_agent.process_json(transaction_id)
        elif detected_format == "PDF": # ADD THIS BLOCK
           await pdf_agent.process_pdf(transaction_id)
           next_step_message = f"Routed to {detected_format} Agent (processing complete)."
        else:
            next_step_message = f"No specific agent for format '{detected_format}' or agent not yet implemented. Classification complete."
            # For unhandled formats, we might still want a basic log
            current_data = shared_memory.get_transaction_data(transaction_id)
            if current_data:
                current_data["final_status"] = "completed_no_specific_agent"
                current_data["agent_processed_by"] = "ClassifierAgent"
                shared_memory.set_transaction_data(transaction_id, current_data)


        # After the specific agent processes, it updates the shared memory.
        # Now, the Action Router picks up the final chained action.
        final_transaction_data = shared_memory.get_transaction_data(transaction_id)
        if final_transaction_data:
            chained_action = final_transaction_data.get("chained_action_triggered")
            print(f"Main App: Chained action from agent for {transaction_id}: {chained_action}")

            # Define proposed_action strings for action_router to match
            if chained_action == "escalate_crm":
                # Ensure data matches what crm/escalate expects
                sender = final_transaction_data.get("extracted_data", {}).get("sender", "N/A")
                issue_request = final_transaction_data.get("extracted_data", {}).get("issue_request", "N/A")
                tone = final_transaction_data.get("extracted_data", {}).get("tone", "N/A")
                await action_router.trigger_action(
                    transaction_id,
                    "CRM_Escalate", # Matches string in action_router
                    {"sender": sender, "issue_request": issue_request, "tone": tone, "source_intent": detected_intent}
                )
            elif chained_action == "log_and_close_crm":
                # Ensure data matches what crm/log_and_close expects
                sender = final_transaction_data.get("extracted_data", {}).get("sender", "N/A")
                issue_request = final_transaction_data.get("extracted_data", {}).get("issue_request", "N/A")
                await action_router.trigger_action(
                    transaction_id,
                    "CRM_LogAndClose", # Matches string in action_router
                    {"sender": sender, "issue_request": issue_request, "source_intent": detected_intent}
                )
            elif chained_action == "Log Alert":
                # Data for risk alert comes from anomaly_details/flagged_conditions
                anomaly_details = final_transaction_data.get("anomaly_details", [])
                flagged_conditions = final_transaction_data.get("flagged_conditions", [])
                
                alert_type = f"{detected_format.upper()}_ANOMALY" if anomaly_details else f"{detected_format.upper()}_FLAG"
                
                # Consolidate all relevant information for the alert
                details_for_alert = {
                    "anomalies": anomaly_details,
                    "flags": flagged_conditions,
                    "intent": detected_intent,
                    "source_format": detected_format,
                    "extracted_data": final_transaction_data.get("extracted_data"), # From Email/JSON agent
                    "pdf_agent_output": final_transaction_data.get("pdf_agent_output"), # From PDF agent
                    "raw_input_preview": final_transaction_data.get("initial_input_preview") # From Classifier
                }
                # Clean up None values before serializing
                details_for_alert = {k: v for k, v in details_for_alert.items() if v is not None}

                await action_router.trigger_action(
                    transaction_id,
                    "Risk_Alert", # Matches string in action_router
                    {"alert_type": alert_type, "details": json.dumps(details_for_alert, indent=2), "source": detected_format, "intent": detected_intent}
                )
            elif chained_action == "escalate_crm_and_risk_alert":
                # Trigger both CRM_Escalate and Risk_Alert
                sender = final_transaction_data.get("extracted_data", {}).get("sender", "N/A")
                issue_request = final_transaction_data.get("extracted_data", {}).get("issue_request", "N/A")
                tone = final_transaction_data.get("extracted_data", {}).get("tone", "N/A")
                
                await action_router.trigger_action(
                    transaction_id,
                    "CRM_Escalate",
                    {"sender": sender, "issue_request": issue_request, "tone": tone, "source_intent": detected_intent}
                )
                await action_router.trigger_action(
                    transaction_id,
                    "Risk_Alert",
                    {"alert_type": "THREATENING_EMAIL", "details": f"Threatening email from {sender} regarding: {issue_request}", "source": detected_format, "intent": detected_intent}
                )
            elif chained_action == "Log Error": # Handles generic errors from agents
                error_message = final_transaction_data.get("error_message", "Unknown error during agent processing.")
                # Also include any available extracted/flagged data for context
                details_for_alert = {
                    "error_message": error_message,
                    "source_format": detected_format,
                    "source_intent": detected_intent,
                    "agent_output": final_transaction_data.get("extracted_data") or final_transaction_data.get("pdf_agent_output"),
                    "flagged_conditions": final_transaction_data.get("flagged_conditions", []) # Ensure this is also passed
                }
                details_for_alert = {k: v for k, v in details_for_alert.items() if v is not None} # Clean up None values
                await action_router.trigger_action(
                    transaction_id,
                    "Risk_Alert", # Log all errors as risk alerts for review
                    {"alert_type": f"{detected_format.upper()}_PROCESSING_ERROR", "details": json.dumps(details_for_alert, indent=2), "source": detected_format, "intent": detected_intent}
                )
            elif chained_action == "None":
                print(f"Action Router: No specific chained action for transaction {transaction_id}.")
                next_step_message = "Classification and processing complete. No chained action triggered."
            else:
                # Fallback for any unhandled chained_action values from agents
                print(f"Action Router: Unrecognized chained action from agent: {chained_action} for transaction {transaction_id}.")
                next_step_message = f"Processing complete, but agent proposed unrecognized action: {chained_action}."
                await action_router.trigger_action(
                    transaction_id,
                    "Risk_Alert", # Log as a system alert
                    {"alert_type": "UNRECOGNIZED_CHAINED_ACTION", "details": f"Agent proposed '{chained_action}' for intent '{detected_intent}'.", "source": "System"}
                )
        else:
            print(f"Action Router: Could not retrieve final transaction data for {transaction_id}.")
            next_step_message = "Processing completed, but final transaction data retrieval failed for action routing."

        return {
            "message": "Input classified and metadata stored.",
            "transaction_id": transaction_id,
            "format": detected_format,
            "intent": detected_intent,
            "next_step": next_step_message
        }
    except HTTPException as e:
        # Update trace for HTTP exceptions if they occur before final trace update
        current_data = shared_memory.get_transaction_data(transaction_id)
        if current_data:
            current_data["final_status"] = "error"
            current_data["error_message"] = f"HTTP Error in main routing: {e.detail}"
            current_data["agent_decision_trace"].append({"agent": "main_router", "step": "http_exception", "details": str(e.detail)})
            shared_memory.set_transaction_data(transaction_id, current_data)
        raise e # Re-raise FastAPI HTTP exceptions
    except Exception as e:
        print(f"An unexpected error occurred in /classify: {e}")
        # Ensure error is logged to shared memory even if an unexpected exception occurs here
        current_data = shared_memory.get_transaction_data(transaction_id)
        if current_data:
            current_data["final_status"] = "error"
            current_data["error_message"] = f"Critical error in main routing: {str(e)}"
            current_data["agent_decision_trace"].append({"agent": "main_router", "step": "critical_error", "details": str(e)})
            shared_memory.set_transaction_data(transaction_id, current_data)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

# --- Simulated External Service Endpoints (for Action Router) ---
@app.post("/crm/escalate")
async def crm_escalate_endpoint(data: dict):
    print(f"CRM: Escalating issue for {data.get('sender', 'N/A')}: {data.get('issue_request', 'N/A')}. Tone: {data.get('tone', 'N/A')}")
    # In a real scenario, this would interact with a CRM API
    return {"status": "success", "message": "Issue escalated in CRM"}

@app.post("/crm/log_and_close")
async def crm_log_and_close_endpoint(data: dict):
    print(f"CRM: Logging and closing issue for {data.get('sender', 'N/A')}: {data.get('issue_request', 'N/A')}")
    # In a real scenario, this would interact with a CRM API
    return {"status": "success", "message": "Issue logged and closed in CRM"}

@app.post("/risk_alert")
async def risk_alert_endpoint(data: dict):
    print(f"RISK: New alert: {data.get('alert_type', 'N/A')} - Details: {data.get('details', 'N/A')}. Source: {data.get('source', 'N/A')}. Intent: {data.get('intent', 'N/A')}")
    # In a real scenario, this would interact with a risk management system
    return {"status": "success", "message": "Risk alert triggered"}