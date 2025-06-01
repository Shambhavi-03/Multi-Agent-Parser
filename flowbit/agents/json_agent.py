# your_project_name/agents/json_agent.py

import json
from typing import Dict, Any, Optional
import jsonschema # Make sure you have 'pip install jsonschema'

from ..core import shared_memory
# from ..core import llm_client # Uncomment only if JSON agent needs LLM for complex anomaly detection

# --- Predefined Schemas for different intents (Example) ---
# These schemas define the expected structure for incoming JSON data.
# You can expand these as needed based on your specific business intents.
JSON_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "RFQ": {
        "type": "object",
        "properties": {
            "request_id": {"type": "string", "description": "Unique identifier for the Request for Quote."},
            "company_name": {"type": "string", "description": "Name of the company making the RFQ."},
            "items": {
                "type": "array",
                "description": "List of items requested.",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string"},
                        "description": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1},
                        "unit": {"type": "string"}
                    },
                    "required": ["item_id", "description", "quantity"]
                }
            },
            "due_date": {"type": "string", "format": "date", "description": "Deadline for quote submission (YYYY-MM-DD)."}
        },
        "required": ["request_id", "company_name", "items", "due_date"],
        "additionalProperties": False # Enforce strict schema, no extra fields
    },
    "Invoice": {
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string"},
            "vendor_name": {"type": "string"},
            "customer_name": {"type": "string"},
            "total_amount": {"type": "number", "minimum": 0},
            "currency": {"type": "string", "pattern": "^(USD|EUR|GBP|INR)$"}, # Example: specific currencies
            "issue_date": {"type": "string", "format": "date"},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1},
                        "unit_price": {"type": "number", "minimum": 0},
                        "line_total": {"type": "number", "minimum": 0}
                    },
                    "required": ["description", "quantity", "unit_price"]
                }
            }
        },
        "required": ["invoice_number", "vendor_name", "total_amount", "currency"],
        "additionalProperties": False
    },
    "Fraud Risk": {
        "type": "object",
        "properties": {
            "alert_id": {"type": "string"},
            "risk_score": {"type": "number", "minimum": 0, "maximum": 100},
            "event_type": {"type": "string", "enum": ["unauthorized_login", "suspicious_transfer", "data_breach_attempt"]},
            "source_ip": {"type": "string", "format": "ipv4"},
            "user_id": {"type": "string"}
        },
        "required": ["alert_id", "risk_score", "event_type"],
        "additionalProperties": False
    }
    # "Other" intent typically doesn't have a strict schema for validation,
    # but you could define a generic one if needed.
}


async def process_json(transaction_id: str):
    """
    Processes a JSON input:
    1. Parses the raw JSON string.
    2. Validates against a schema based on the classified intent.
    3. Flags anomalies (e.g., schema validation errors, business rule violations).
    4. Logs alerts in memory if anomalies are detected.
    """
    print(f"JSON Agent: Processing transaction {transaction_id}...")

    transaction_data = shared_memory.get_transaction_data(transaction_id)
    if not transaction_data:
        print(f"JSON Agent: Error - Transaction {transaction_id} not found in memory.")
        return

    raw_json_str = transaction_data.get("raw_input_str")
    detected_intent = transaction_data.get("classifier_output", {}).get("intent")

    extracted_data = {}
    chained_action = "None"
    decision_trace = transaction_data.get("agent_decision_trace", [])
    error_occurred = False
    anomaly_details = []

    # Ensure raw_json_str exists for processing
    if not raw_json_str:
        error_msg = "JSON Agent: raw_input_str (JSON content) not found for processing."
        print(error_msg)
        anomaly_details.append({"type": "MISSING_JSON_CONTENT", "message": error_msg})
        error_occurred = True
        decision_trace.append({"agent": "JsonAgent", "step": "error", "details": error_msg})

        # Update memory immediately if no content
        shared_memory.update_transaction_data(transaction_id, {
            "agent_processed_by": "JsonAgent",
            "extracted_data": extracted_data,
            "chained_action_triggered": "Log Alert",
            "agent_decision_trace": decision_trace,
            "json_agent_status": "failed",
            "anomaly_details": anomaly_details,
            "error_message": error_msg
        })
        return # Exit early

    try:
        # 1. Parse JSON content
        try:
            json_data = json.loads(raw_json_str)
            extracted_data["parsed_json"] = json_data
            decision_trace.append({"agent": "JsonAgent", "step": "json_parsed", "details": "Successfully parsed JSON content."})
        except json.JSONDecodeError as e:
            error_msg = f"JSON Agent: Invalid JSON format: {e}"
            print(error_msg)
            anomaly_details.append({"type": "JSON_PARSE_ERROR", "message": str(e)})
            error_occurred = True
            decision_trace.append({"agent": "JsonAgent", "step": "json_parse_error", "details": error_msg})
            # If JSON is invalid, stop here and log the error.
            chained_action = "Log Alert"
            raise # Re-raise to go to outer exception handler for unified logging

        # 2. Validate against schema if intent is recognized and a schema exists
        schema = JSON_SCHEMAS.get(detected_intent)
        if schema:
            try:
                jsonschema.validate(instance=json_data, schema=schema)
                decision_trace.append({"agent": "JsonAgent", "step": "schema_validation", "details": f"Validated against {detected_intent} schema: OK."})
            except jsonschema.ValidationError as e:
                error_msg = f"JSON Agent: Schema validation failed for intent '{detected_intent}': {e.message}"
                print(error_msg)
                anomaly_details.append({"type": "SCHEMA_VALIDATION_ERROR", "message": e.message, "path": list(e.path)})
                error_occurred = True
                decision_trace.append({"agent": "JsonAgent", "step": "schema_validation_error", "details": error_msg})
            except Exception as e: # Catch any other errors during schema validation
                error_msg = f"JSON Agent: Unexpected error during schema validation: {e}"
                print(error_msg)
                anomaly_details.append({"type": "SCHEMA_GENERIC_ERROR", "message": str(e)})
                error_occurred = True
                decision_trace.append({"agent": "JsonAgent", "step": "schema_generic_error", "details": error_msg})
        else:
            decision_trace.append({"agent": "JsonAgent", "step": "schema_validation_skipped", "details": f"No specific schema defined for intent '{detected_intent}'."})

        # 3. Custom Anomaly Detection (Business Logic)
        # This is where you'd add specific checks beyond schema validation.
        # Example: For an RFQ, check if quantity is positive for any item.
        if detected_intent == "RFQ" and not anomaly_details: # Only run if no critical anomalies yet
            items = json_data.get("items", [])
            for i, item in enumerate(items):
                if item.get("quantity") is not None and item.get("quantity") <= 0:
                    anomaly_details.append({
                        "type": "BUSINESS_RULE_VIOLATION",
                        "rule": "RFQ_QUANTITY_POSITIVE",
                        "message": f"RFQ item at index {i} has non-positive quantity: {item.get('quantity')}",
                        "path": f"items[{i}].quantity"
                    })
                    error_occurred = True
            if anomaly_details: # If any business rule anomalies are found here
                decision_trace.append({"agent": "JsonAgent", "step": "business_rule_check", "details": "Business rule anomalies detected for RFQ."})

        # Example: For an Invoice, check if total_amount matches sum of line_items (if line_items exist)
        if detected_intent == "Invoice" and not anomaly_details:
            total_amount_invoice = json_data.get("total_amount")
            line_items = json_data.get("line_items")
            if isinstance(total_amount_invoice, (int, float)) and isinstance(line_items, list) and line_items:
                calculated_total = sum(item.get("line_total", 0) for item in line_items if isinstance(item.get("line_total"), (int, float)))
                # Allow a small floating point difference
                if abs(total_amount_invoice - calculated_total) > 0.01:
                    anomaly_details.append({
                        "type": "BUSINESS_RULE_VIOLATION",
                        "rule": "INVOICE_TOTAL_MISMATCH",
                        "message": f"Invoice total {total_amount_invoice} does not match sum of line items {calculated_total}.",
                        "details": {"invoice_total": total_amount_invoice, "calculated_total": calculated_total}
                    })
                    error_occurred = True
            if anomaly_details:
                decision_trace.append({"agent": "JsonAgent", "step": "business_rule_check", "details": "Business rule anomalies detected for Invoice."})


        # 4. Determine Chained Action based on anomalies
        if anomaly_details:
            chained_action = "Log Alert" # Trigger a risk alert or internal logging
            decision_trace.append({"agent": "JsonAgent", "step": "action_decision", "details": "Anomalies detected, triggering 'Log Alert'."})
        else:
            # If valid JSON with no anomalies, consider it processed successfully.
            # The next action would depend on the business workflow for valid JSON.
            # For now, it's 'None' meaning no further automated action *by this agent*.
            chained_action = "None"
            decision_trace.append({"agent": "JsonAgent", "step": "action_decision", "details": "JSON valid and no anomalies detected."})

    except Exception as e:
        # Catch any other unexpected errors during processing
        error_msg = f"JSON Agent: General processing error for transaction {transaction_id}: {e}"
        print(error_msg)
        chained_action = "Log Error" # A more severe error that might need human review
        error_occurred = True
        anomaly_details.append({"type": "UNEXPECTED_PROCESSING_ERROR", "message": str(e)})
        decision_trace.append({"agent": "JsonAgent", "step": "general_error", "details": error_msg})

    # 5. Update Shared Memory
    update_data = {
        "agent_processed_by": "JsonAgent",
        "extracted_data": extracted_data,
        "chained_action_triggered": chained_action,
        "agent_decision_trace": transaction_data.get("agent_decision_trace", []) + decision_trace, # Append to existing trace
        "json_agent_status": "completed" if not error_occurred else "failed",
        "anomaly_details": anomaly_details # Store all detected anomalies
    }
    if error_occurred:
        # Consolidate error messages from anomalies for clarity
        full_error_summary = "; ".join([f"{a['type']}: {a['message']}" for a in anomaly_details])
        update_data["error_message"] = f"JSON Agent failed: {full_error_summary}"

    shared_memory.update_transaction_data(transaction_id, update_data)
    print(f"JSON Agent: Finished processing transaction {transaction_id}. Action: {chained_action}")