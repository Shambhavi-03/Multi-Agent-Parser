# your_project_name/core/action_router.py

import httpx # Changed from 'requests' to 'httpx' for async compatibility
from typing import Dict, Any

from . import shared_memory # Import shared_memory for updating trace

FASTAPI_BASE_URL = "http://localhost:8000" # Base URL for your own FastAPI app's external service endpoints

async def trigger_action(transaction_id: str, proposed_action: str, action_details: Dict[str, Any]):
    """
    Triggers an external action based on the proposed_action.
    Updates the shared memory trace with the action outcome.
    """
    print(f"Action Router: Triggering action '{proposed_action}' for transaction {transaction_id}")
    action_status = "failed"
    action_response = {}
    endpoint = None

    try:
        async with httpx.AsyncClient() as client: # Use httpx.AsyncClient for async requests
            if proposed_action == "CRM_Escalate":
                endpoint = f"{FASTAPI_BASE_URL}/crm/escalate"
                response = await client.post(endpoint, json=action_details, timeout=30) # Add timeout
            elif proposed_action == "CRM_LogAndClose":
                endpoint = f"{FASTAPI_BASE_URL}/crm/log_and_close"
                response = await client.post(endpoint, json=action_details, timeout=30)
            elif proposed_action == "Risk_Alert":
                endpoint = f"{FASTAPI_BASE_URL}/risk_alert"
                response = await client.post(endpoint, json=action_details, timeout=30)
            else:
                action_status = "unsupported_action"
                action_response = {"message": f"Unsupported action: {proposed_action}"}
                print(f"Action Router: {action_response['message']}")
                # No HTTP call needed for unsupported action, so skip raising for status
                response = None # Indicate no response object to avoid AttributeError later

            if response: # Only process response if an endpoint was triggered
                response.raise_for_status() # Raises httpx.HTTPStatusError for 4xx/5xx responses
                action_response = response.json()
                action_status = "success"
                print(f"Action Router: Action '{proposed_action}' successful. Response: {action_response}")

    except httpx.ConnectError: # Specific httpx connection error
        print(f"Action Router Error: Could not connect to FastAPI at {FASTAPI_BASE_URL}. Is it running?")
        action_status = "connection_error"
        action_response = {"error": "FastAPI backend connection refused"}
    except httpx.RequestError as e: # Catch all other httpx request errors (e.g., timeout, HTTP status)
        print(f"Action Router Error during action '{proposed_action}' to {endpoint}: {e}")
        action_status = "http_error"
        action_response = {"error": str(e), "response_text": getattr(e.response, 'text', 'No response text')}
    except Exception as e:
        print(f"Action Router Error: An unexpected error occurred for '{proposed_action}': {e}")
        action_status = "internal_error"
        action_response = {"error": str(e)}

    # Update shared memory with action trace
    trace_entry = {
        "agent": "action_router",
        "step": proposed_action,
        "status": action_status,
        "details": action_details,
        "response": action_response
    }
    
    current_data = shared_memory.get_transaction_data(transaction_id)
    if current_data:
        if "agent_decision_trace" not in current_data:
            current_data["agent_decision_trace"] = []
        current_data["agent_decision_trace"].append(trace_entry)
        shared_memory.set_transaction_data(transaction_id, current_data)
    else:
        print(f"Action Router Warning: Transaction {transaction_id} not found in shared memory for trace update.")