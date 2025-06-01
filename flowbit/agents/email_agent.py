# your_project_name/agents/email_agent.py

import json
import email
from email.header import decode_header
from typing import Dict, Any, Optional
import re

from ..core import shared_memory
from ..core import llm_client

# --- LLM Prompt for Email Extraction ---
EMAIL_EXTRACTION_PROMPT = """
You are an expert AI assistant specializing in extracting structured information from email communications.
Your goal is to accurately identify and extract the following fields from the provided email content.
Respond ONLY with a JSON object.

Fields to extract:
- sender: The email address of the sender.
- urgency: Categorize the email's urgency as one of: "low", "medium", "high", "critical". Consider keywords like "urgent", "ASAP", "immediate", "critical issue", deadlines, or lack thereof.
- issue_request: A concise summary (1-3 sentences) of the main issue or request presented in the email.
- tone: Characterize the overall tone of the email as one of: "polite", "neutral", "escalation", "threatening", "frustrated", "inquiring".

---
Email Content:
{email_content}

---
JSON Output:
"""

async def process_email(transaction_id: str):
    """
    Processes an email input, extracts structured fields, identifies tone and urgency,
    and determines a follow-up action.
    """
    print(f"Email Agent: Processing transaction {transaction_id}...")
    
    # 1. Retrieve raw email content and initial classification from shared memory
    transaction_data = shared_memory.get_transaction_data(transaction_id)
    if not transaction_data:
        print(f"Email Agent: Error - Transaction {transaction_id} not found in memory.")
        # Update memory with error status if needed
        return

    raw_email_str = transaction_data.get("raw_input_str")
    if not raw_email_str:
        error_msg = "Email Agent: raw_input_str not found for email processing."
        print(error_msg)
        shared_memory.update_transaction_data(transaction_id, {
            "agent_processed_by": "EmailAgent",
            "chained_action_triggered": "Log Error",
            "error_message": error_msg,
            "agent_decision_trace": transaction_data.get("agent_decision_trace", []) + [
                {"agent": "EmailAgent", "step": "error", "details": error_msg}
            ]
        })
        return

    extracted_fields = {}
    chained_action = "None"
    decision_trace = []
    error_occurred = False

    try:
        # Initial parsing to get subject and body more reliably for LLM
        msg = email.message_from_string(raw_email_str)
        subject_header = msg.get("Subject", "")
        # Decode subject header properly
        decoded_subject_parts = decode_header(subject_header)
        subject = ""
        for part, charset in decoded_subject_parts:
            if isinstance(part, bytes):
                try:
                    subject += part.decode(charset if charset else 'utf-8')
                except UnicodeDecodeError:
                    subject += part.decode('latin-1', errors='ignore') # Fallback
            else:
                subject += part
        
        body_content = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))
                # Look for plain text body, avoiding attachments
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    try:
                        body_content = part.get_payload(decode=True).decode('utf-8')
                        break
                    except Exception as e:
                        print(f"Email Agent: Error decoding email part: {e}")
                        body_content = "[Body content decode error]"
        else:
            try:
                body_content = msg.get_payload(decode=True).decode('utf-8')
            except Exception as e:
                print(f"Email Agent: Error decoding single part email: {e}")
                body_content = "[Body content decode error]"

        # Combine subject and body for LLM processing
        llm_input_content = f"Subject: {subject}\n\n{body_content[:2000]}" # Limit size for LLM
        decision_trace.append({"agent": "EmailAgent", "step": "extracted_for_llm", "details": {"subject": subject, "body_snippet": llm_input_content[:500] + "..."}})

        # 2. Use LLM to extract structured fields
        llm_response_json_str = await llm_client.call_gemini_for_extraction(
            prompt_template=EMAIL_EXTRACTION_PROMPT,
            text_to_process=llm_input_content
        )
        
        try:
            # Assuming call_ollama_for_extraction will return a dictionary, not a string
            # If it returns a string, you'll need `json.loads` here.
            # Let's adjust llm_client.py's call_ollama_for_extraction to return Dict[str, Any]
            extracted_fields = llm_response_json_str # Directly assign if it's already a dict
            if isinstance(llm_response_json_str, str): # Fallback if LLM client returns string
                extracted_fields = json.loads(llm_response_json_str)

        except json.JSONDecodeError as e:
            error_msg = f"Email Agent: LLM response was not valid JSON: {e}. Raw LLM output: {llm_response_json_str[:200]}"
            print(error_msg)
            extracted_fields = {"parse_error": error_msg}
            error_occurred = True
            decision_trace.append({"agent": "EmailAgent", "step": "llm_parse_error", "details": error_msg})
        except Exception as e:
            error_msg = f"Email Agent: Unexpected error processing LLM response: {e}"
            print(error_msg)
            extracted_fields = {"processing_error": error_msg}
            error_occurred = True
            decision_trace.append({"agent": "EmailAgent", "step": "llm_processing_error", "details": error_msg})


        # 3. Decisioning based on extracted fields (tone + urgency)
        if not error_occurred:
            urgency = extracted_fields.get("urgency", "").lower()
            tone = extracted_fields.get("tone", "").lower()

            if urgency == "critical" or urgency == "high" and (tone == "escalation" or tone == "threatening" or tone == "frustrated"):
                chained_action = "escalate_crm"
                decision_trace.append({"agent": "EmailAgent", "step": "action_decision", "details": "Escalate CRM due to high urgency and critical/escalation/threatening tone."})
            elif urgency == "low" or urgency == "medium":
                chained_action = "log_and_close_crm"
                decision_trace.append({"agent": "EmailAgent", "step": "action_decision", "details": "Log and close CRM due to low/medium urgency."})
            else:
                chained_action = "log_and_close_crm" # Default routine action if no specific match
                decision_trace.append({"agent": "EmailAgent", "step": "action_decision", "details": "Default log and close CRM action."})
            
            # Additional check for threatening tone regardless of urgency for potential immediate flagging
            if tone == "threatening":
                chained_action = "escalate_crm_and_risk_alert" # Combined action
                decision_trace.append({"agent": "EmailAgent", "step": "action_decision", "details": "Threatening tone detected, escalating CRM and triggering risk alert."})


    except Exception as e:
        error_msg = f"Email Agent: General processing error for transaction {transaction_id}: {e}"
        print(error_msg)
        chained_action = "Log Error"
        error_occurred = True
        decision_trace.append({"agent": "EmailAgent", "step": "general_error", "details": error_msg})

    # 4. Update Shared Memory
    update_data = {
        "agent_processed_by": "EmailAgent",
        "extracted_data": extracted_fields,
        "chained_action_triggered": chained_action,
        "agent_decision_trace": transaction_data.get("agent_decision_trace", []) + decision_trace,
        "email_agent_status": "completed" if not error_occurred else "failed"
    }
    if error_occurred:
        update_data["error_message"] = error_msg
        
    shared_memory.update_transaction_data(transaction_id, update_data)
    print(f"Email Agent: Finished processing transaction {transaction_id}. Action: {chained_action}")