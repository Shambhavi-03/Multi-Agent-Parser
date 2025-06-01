# your_project_name/agents/classifier_agent.py

import json
import email
import io
import re
import base64
import pypdf # Make sure you have 'pip install pypdf'
from typing import Optional
from fastapi import UploadFile, HTTPException

from ..core import shared_memory
from ..core import llm_client

# --- LLM Prompt for Intent Classification ---
CLASSIFIER_PROMPT = """
You are an intelligent AI system specialized in classifying business communications.
Your task is to identify the primary business intent from the provided text.

Choose *only one* of the following categories: RFQ, Complaint, Invoice, Regulation, Fraud Risk, Other.
Provide your answer as a single word, which is the category name.

---
Examples:

Text: "Subject: Urgent issue with order #123. The product delivered is completely broken and unusable. I am very dissatisfied with the quality and demand a refund."
Intent: Complaint

Text: "Dear Vendor, we are requesting a detailed quote for 500 units of Model XYZ, part number M-123. Please include lead times and bulk discounts. We require delivery by October 1st."
Intent: RFQ

Text: "Invoice #2023-001\\nDate: May 30, 2025\\nTotal Amount Due: $5,500.00\\nFor services rendered: Software Development Phase 1."
Intent: Invoice

Text: "This document outlines our company's adherence to the new GDPR regulations regarding data privacy and consent. It details our updated policies."
Intent: Regulation

Text: "Immediate action required: Suspicious activity detected on account 123456. An unauthorized large transfer of funds was attempted from an unknown IP address."
Intent: Fraud Risk

Text: "Hello team, just a quick update on the project status. We are on track for the next milestone."
Intent: Other

---
Text to classify:
{text_to_classify}

Intent:
"""

async def classify_input_data(
    transaction_id: str,
    timestamp: str,
    file: Optional[UploadFile],
    text_input: Optional[str]
) -> dict:
    """
    Handles the core logic of the Classifier Agent:
    - Reads input (file or text)
    - Detects format
    - Extracts relevant text for LLM
    - Classifies intent using LLM (Ollama)
    - Stores initial data to shared memory
    """
    raw_content_bytes: Optional[bytes] = None
    raw_content_str: Optional[str] = None
    detected_format = "Other"
    text_for_llm = ""
    initial_data_raw_pdf_base64: Optional[str] = None # For storing PDF bytes

    # 1. Input Reception and Initial Format Heuristics
    if file:
        raw_content_bytes = await file.read()
        content_type = file.content_type
        filename = file.filename

        if content_type == "application/json" or (filename and filename.endswith(".json")):
            detected_format = "JSON"
            raw_content_str = raw_content_bytes.decode("utf-8")
            text_for_llm = raw_content_str
        elif content_type == "application/pdf" or (filename and filename.endswith(".pdf")):
            detected_format = "PDF"
            initial_data_raw_pdf_base64 = base64.b64encode(raw_content_bytes).decode('utf-8')
            # Attempt preliminary text extraction for LLM classification
            try:
                reader = pypdf.PdfReader(io.BytesIO(raw_content_bytes))
                extracted_text = ""
                for i, page in enumerate(reader.pages):
                    extracted_text += page.extract_text() or ""
                    if len(extracted_text) > 2000:
                        break
                text_for_llm = extracted_text[:2000]
                if not text_for_llm.strip(): # Fallback if no text extracted (e.g., scanned PDF)
                    print(f"Warning: No readable text extracted from PDF '{filename}'. Using filename/type for LLM.")
                    text_for_llm = f"PDF file: {filename}. Content type: {content_type}. (No readable text content)"
            except Exception as e:
                print(f"Error extracting text from PDF '{filename}' for classification: {e}")
                text_for_llm = f"PDF file (extraction failed): {filename}. Content type: {content_type}."
            raw_content_str = f"PDF file: {filename} (Content encoded in raw_input_pdf_base64)" # String placeholder
        elif content_type == "message/rfc822" or (filename and filename.endswith(".eml")):
            detected_format = "Email"
            raw_content_str = raw_content_bytes.decode("utf-8")
            msg = email.message_from_string(raw_content_str)
            subject = msg.get("Subject", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    cdispo = str(part.get('Content-Disposition'))
                    if ctype == 'text/plain' and 'attachment' not in cdispo:
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()
            text_for_llm = f"Subject: {subject}\n\n{body[:500]}"
        else: # Other file types, treat as plain text
            raw_content_str = raw_content_bytes.decode("utf-8")
            detected_format = "Other_File"
            text_for_llm = raw_content_str[:1000]

    elif text_input: # Direct text input
        raw_content_str = text_input
        try: # Try to infer JSON
            json.loads(text_input)
            detected_format = "JSON"
            text_for_llm = text_input
        except json.JSONDecodeError: # Else, check for email patterns
            if re.search(r"From:\s*.*@.*\nSubject:", text_input, re.IGNORECASE | re.MULTILINE):
                detected_format = "Email"
                subject_match = re.search(r"Subject:\s*(.*)", text_input, re.IGNORECASE)
                subject = subject_match.group(1).strip() if subject_match else ""
                body = text_input
                text_for_llm = f"Subject: {subject}\n\n{body[:500]}"
            else: # Otherwise, it's just general text
                detected_format = "Other_Text"
                text_for_llm = text_input[:1000]
    else:
        raise HTTPException(status_code=400, detail="No input provided (file or text_input).")

    # 2. LLM-Powered Intent Classification
    detected_intent = "Other"
    if text_for_llm:
        # Pass the specific prompt to the LLM client
        llm_classified_intent = await llm_client.call_gemini_for_classification(
            prompt_template=CLASSIFIER_PROMPT,
            text_to_classify=text_for_llm
        )

        if llm_classified_intent == "Ollama_Error":
            detected_intent = "Other"
            print("Warning: Ollama connection error. Intent defaulted to 'Other'.")
        else:
            detected_intent = llm_classified_intent
    else:
        print("Warning: No text available for LLM classification. Setting intent to 'Other'.")
        detected_intent = "Other"

    # 3. Store to Shared Memory
    initial_data = {
        "transaction_id": transaction_id,
        "timestamp": timestamp,
        "source_type": detected_format,
        "raw_input_str": raw_content_str,
        "classifier_output": {
            "format": detected_format,
            "intent": detected_intent
        },
        "agent_decision_trace": [
            {"agent": "classifier", "step": "initial_classification", "details": {"format": detected_format, "intent": detected_intent, "llm_text_sent_snippet": text_for_llm[:500] + "..." if len(text_for_llm) > 500 else text_for_llm}}
        ]
    }

    if detected_format == "PDF" and initial_data_raw_pdf_base64:
        initial_data["raw_input_pdf_base64"] = initial_data_raw_pdf_base64

    shared_memory.set_transaction_data(transaction_id, initial_data)

    return {"format": detected_format, "intent": detected_intent}