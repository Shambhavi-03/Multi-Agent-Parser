# your_project_name/agents/pdf_agent.py

import io
import base64
import re
import pypdf
from typing import Dict, Any, Optional
import json

from ..core import shared_memory
from ..core import llm_client
from ..models.schemas import INVOICE_JSON_SCHEMA # Import the schema

# --- LLM Prompt for Invoice Data Extraction ---
# This prompt guides the LLM to extract structured invoice data from the provided text.
# It explicitly asks for JSON output matching the schema.
INVOICE_EXTRACTION_PROMPT = """
You are an expert financial assistant. Your task is to extract structured invoice data from the provided text.
The output MUST be a JSON object that strictly adheres to the following JSON schema.
If a field cannot be found, omit it or set it to null if the schema requires it.
For line items, infer them based on context if not explicitly listed as "description", "quantity", "unit_price".

JSON Schema:
{json_schema}

Invoice Text:
{invoice_text}

Extracted Invoice Data (JSON):
"""

# --- LLM Prompt for Policy Compliance Keyword Detection ---
# This prompt helps identify relevant keywords in policy documents.
POLICY_KEYWORD_PROMPT = """
You are a compliance officer. Your task is to review the provided policy document text and identify if it explicitly mentions any of the following critical compliance terms: "GDPR", "FDA", "HIPAA", "PCI DSS", "ISO 27001", "NIST".
List all mentioned terms found. If no terms are found, state "None".

Policy Document Text:
{policy_text}

Mentioned Compliance Terms (comma-separated, e.g., GDPR, HIPAA):
"""

async def process_pdf(transaction_id: str):
    """
    Processes a PDF input:
    - Retrieves raw PDF bytes from shared memory.
    - Determines if it's an Invoice or Regulation based on initial classification.
    - Extracts data using PDF parsers and/or LLM.
    - Flags conditions (e.g., large invoice total, compliance keywords).
    - Updates shared memory with extracted data and flags.
    - Proposes a chained action.
    """
    print(f"PDF Agent: Processing transaction {transaction_id}")
    transaction_data = shared_memory.get_transaction_data(transaction_id)

    if not transaction_data:
        print(f"PDF Agent: Error - Transaction data not found for {transaction_id}")
        await _update_and_flag_error(transaction_id, "PDF Agent: Transaction data not found.")
        return

    detected_intent = transaction_data.get("classifier_output", {}).get("intent")
    raw_pdf_base664 = transaction_data.get("raw_input_pdf_base64")

    if not raw_pdf_base664:
        print(f"PDF Agent: Error - No raw PDF content found for {transaction_id}")
        await _update_and_flag_error(transaction_id, "PDF Agent: No raw PDF content found.")
        return

    pdf_bytes = base64.b64decode(raw_pdf_base664)
    extracted_text = ""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        for i, page in enumerate(reader.pages):
            extracted_text += page.extract_text() or ""
            # Limit text extraction to prevent excessively long LLM calls
            if len(extracted_text) > 5000: # Adjust limit as needed
                break
    except Exception as e:
        print(f"PDF Agent: Error extracting text from PDF for {transaction_id}: {e}")
        await _update_and_flag_error(transaction_id, f"PDF Agent: Failed to extract text from PDF: {e}")
        return

    pdf_agent_output = {
        "extracted_text_snippet": extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text,
        "full_text_extracted": len(extracted_text) > 0,
        "processed_by": "PDFAgent"
    }
    flagged_conditions = []
    chained_action = "None"
    error_message = None

    if detected_intent == "Invoice":
        print(f"PDF Agent: Intent is 'Invoice'. Attempting structured extraction for {transaction_id}...")
        extracted_invoice_data = {}
        try:
            # Format the prompt directly, passing the schema and text
            formatted_invoice_prompt = INVOICE_EXTRACTION_PROMPT.format(
                json_schema=json.dumps(INVOICE_JSON_SCHEMA, indent=2),
                invoice_text=extracted_text
            )
            llm_result = await llm_client.call_gemini_for_extraction(
                prompt_template=formatted_invoice_prompt,
                text_to_process=None # No need for text_to_process as prompt is fully formatted
            )

            if llm_result.get("error"):
                raise ValueError(f"LLM extraction error: {llm_result['error']}")
            
            # The llm_client should return a dict, and for JSON output, it should be the parsed JSON
            extracted_invoice_data = llm_result 
            pdf_agent_output["extracted_invoice_data"] = extracted_invoice_data

            total_amount = extracted_invoice_data.get("total_amount")
            if total_amount is not None and isinstance(total_amount, (int, float)) and total_amount > 10000:
                flagged_conditions.append({"type": "Invoice_HighValue", "value": total_amount, "threshold": 10000})
                chained_action = "Log Alert" # Trigger an alert for high value invoices

        except Exception as e:
            error_message = f"PDF Agent: Error extracting invoice data: {e}"
            print(error_message)
            flagged_conditions.append({"type": "Extraction_Error", "details": str(e)})
            chained_action = "Log Error" # Log error if extraction fails

    elif detected_intent == "Regulation":
        print(f"PDF Agent: Intent is 'Regulation'. Checking for compliance keywords for {transaction_id}...")
        # Call LLM for compliance keyword detection
        formatted_policy_prompt = POLICY_KEYWORD_PROMPT.format(policy_text=extracted_text)
        llm_result = await llm_client.call_ollama_for_extraction(
            prompt_template=formatted_policy_prompt,
            text_to_process=None # No need for text_to_process as prompt is fully formatted
        )
        
        if llm_result.get("error"):
            error_message = f"PDF Agent: LLM error during compliance keyword check: {llm_result['error']}"
            print(error_message)
            flagged_conditions.append({"type": "LLM_Error_Compliance", "details": error_message})
            chained_action = "Log Error"
        else:
            # Expecting 'response' key from llm_client if no JSON was found
            compliance_keywords_str = llm_result.get("response", "") 
            found_terms = [term.strip() for term in compliance_keywords_str.split(',') if term.strip() and term.strip().lower() != 'none']
            
            if found_terms:
                flagged_conditions.append({"type": "Compliance_Keyword_Detected", "terms": found_terms})
                chained_action = "Log Alert" # Trigger an alert for specific compliance terms
            
            pdf_agent_output["detected_compliance_terms"] = found_terms

    else:
        print(f"PDF Agent: Intent '{detected_intent}' not specifically handled for PDF. No structured extraction or flagging.")
        pdf_agent_output["status"] = "No specific PDF processing for this intent."
        chained_action = "None" # No action for unhandled PDF types

    # Update shared memory
    update_fields = {
        "pdf_agent_output": pdf_agent_output,
        "flagged_conditions": flagged_conditions,
        "chained_action_triggered": chained_action,
        "final_status": "processed_by_pdf_agent"
    }
    if error_message:
        update_fields["error_message"] = error_message
        update_fields["final_status"] = "pdf_agent_error"

    shared_memory.update_transaction_data(transaction_id, update_fields)
    print(f"PDF Agent: Finished processing {transaction_id}. Chained action: {chained_action}")

async def _update_and_flag_error(transaction_id: str, message: str):
    """Helper to update shared memory with an error and propose 'Log Error' action."""
    shared_memory.update_transaction_data(transaction_id, {
        "pdf_agent_output": {"status": "failed", "error": message},
        "flagged_conditions": [{"type": "Agent_Error", "details": message}],
        "chained_action_triggered": "Log Error",
        "error_message": message,
        "final_status": "pdf_agent_error"
    })
    print(f"PDF Agent Error for {transaction_id}: {message}")