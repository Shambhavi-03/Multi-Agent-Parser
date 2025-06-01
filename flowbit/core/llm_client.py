import os
import json
import re
import logging
from typing import Dict, Any, Optional

import google.generativeai as genai
# We don't need to import httpx directly here as google-generativeai's async methods handle it.

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Gemini Configuration ---
# Global variable for the Gemini model instance.
# This ensures the model is initialized only once when the module is loaded.
_gemini_model = None

def _initialize_gemini_model():
    """
    Initializes the Gemini model globally.
    This function will be called automatically when this module is imported.
    """
    global _gemini_model
    if _gemini_model is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logging.error("GEMINI_API_KEY environment variable not set. Please set your Gemini API key.")
            raise ValueError("GEMINI_API_KEY environment variable not set. Gemini model cannot be initialized.")
        
        genai.configure(api_key=api_key)
        
        # We'll use gemini-1.5-flash-latest for faster responses.
        # You can switch to 'gemini-1.5-pro-latest' for more complex reasoning if needed.
        _gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest') 
        logging.info(f"Gemini LLM initialized with model: {_gemini_model.model_name}")

# Initialize the model as soon as this module is imported.
# It's crucial that `load_dotenv()` in `main_app.py` runs BEFORE this line.
_initialize_gemini_model()


async def call_gemini_for_classification(prompt_template: str, text_to_classify: str) -> str:
    """
    Makes an asynchronous call to the Gemini API for classification.
    The function name is kept as 'call_ollama_for_classification' to avoid
    changes in other agent files that call it.
    
    Args:
        prompt_template (str): The prompt string with a placeholder for the text to classify.
        text_to_classify (str): The input text to be classified.
        
    Returns:
        str: The classified intent (e.g., "Invoice", "Fraud Risk").
    """
    if _gemini_model is None:
        logging.error("Gemini model not initialized in call_ollama_for_classification.")
        return "LLM_Error" 

    try:
        formatted_prompt = prompt_template.format(text_to_classify=text_to_classify)

        # Gemini models often perform best with content structured as a conversation.
        response = await _gemini_model.generate_content_async(
            contents=[{"role": "user", "parts": [{"text": formatted_prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,      # Low temperature for deterministic classification
                max_output_tokens=50, # Classification responses are typically short
            ),
            safety_settings=[ # Recommended safety settings to allow broader responses
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        
        intent = ""
        # Check if any candidates (responses) were returned by the LLM.
        # Responses might be blocked by safety settings or other issues.
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text'):
                    intent = part.text
                    break
        else:
            # Log reasons for blocked responses (e.g., safety feedback).
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                logging.warning(f"Gemini blocked response for classification. Feedback: {response.prompt_feedback}")
            else:
                logging.warning("Gemini returned no candidates for classification.")
            return "LLM_Blocked" # Indicate a blocked response

        # Basic cleanup: remove common prefixes/suffixes LLMs might add.
        intent = intent.replace('Intent: ', '').strip()
        intent = intent.replace('"', '').strip()
        intent = intent.split('\n')[0].strip() # Take only the first line

        # Validate the extracted intent against your predefined categories.
        valid_llm_intents = ["RFQ", "Complaint", "Invoice", "Regulation", "Fraud Risk", "Other"]
        if intent not in valid_llm_intents:
            logging.warning(f"LLM returned unrecognized intent '{intent}'. Defaulting to 'Other'. Full response: {intent}")
            return "Other"

        return intent

    except genai.types.BlockedPromptException as e:
        logging.error(f"Gemini API blocked the prompt for classification: {e}")
        return "LLM_Blocked"
    except genai.types.APIError as e:
        logging.error(f"Gemini API error during classification: {e}")
        return "Gemini_API_Error"
    except Exception as e:
        logging.error(f"An unexpected error occurred during classification call: {e}", exc_info=True)
        return "LLM_Error"


async def call_gemini_for_extraction(prompt_template: str, text_to_process: Optional[str] = None) -> Dict[str, Any]:
    """
    Calls the Gemini API for structured data extraction and parses the JSON response.
    The function name is kept as 'call_ollama_for_extraction' to avoid
    changes in other agent files that call it.
    
    It can either take a text_to_process to format the prompt, or assume the
    prompt_template is already fully formatted.
    
    Args:
        prompt_template (str): The prompt string, possibly with a placeholder.
        text_to_process (Optional[str]): The text to be processed and extracted from.
        
    Returns:
        Dict[str, Any]: The extracted data as a dictionary, or an error dictionary.
    """
    if _gemini_model is None:
        logging.error("Gemini model not initialized in call_ollama_for_extraction.")
        return {"error": "LLM_Error"} 

    try:
        # Determine the final prompt by formatting if a placeholder and text_to_process are present.
        match_placeholder = re.search(r'\{(\w+)\}', prompt_template)
        
        if match_placeholder and text_to_process is not None:
            placeholder_name = match_placeholder.group(1)
            formatted_prompt = prompt_template.format(**{placeholder_name: text_to_process})
        else:
            formatted_prompt = prompt_template
        
        # Instruct Gemini to respond in JSON format directly within the prompt.
        response = await _gemini_model.generate_content_async(
            contents=[{"role": "user", "parts": [{"text": formatted_prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,       # Low temperature for structured output
                max_output_tokens=1000, # Allow sufficient tokens for JSON output
            ),
            safety_settings=[ # Recommended safety settings
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )

        json_str_response = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text'):
                    json_str_response = part.text
                    break
        else:
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                logging.warning(f"Gemini blocked response for extraction. Feedback: {response.prompt_feedback}")
            else:
                logging.warning("Gemini returned no candidates for extraction.")
            return {"error": "LLM_Blocked"}

        # Robust JSON parsing: Find the first '{' and last '}' to isolate the JSON.
        # This handles cases where the LLM might include text before/after the JSON,
        # or markdown code blocks like ```json{...}```.
        start_idx = json_str_response.find('{')
        end_idx = json_str_response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_part = json_str_response[start_idx : end_idx + 1]
            extracted_data = json.loads(json_part)
        else:
            # If no valid JSON object is found, return the raw response content as a dictionary.
            # This is useful for prompts that might just return a plain string (e.g., keyword lists).
            logging.warning(f"No valid JSON object found in LLM response for extraction. Returning raw response string. Response snippet: {json_str_response[:200]}...")
            return {"response": json_str_response.strip()}

        return extracted_data

    except genai.types.BlockedPromptException as e:
        logging.error(f"Gemini API blocked the prompt for extraction: {e}")
        return {"error": "LLM_Blocked"}
    except genai.types.APIError as e:
        logging.error(f"Gemini API error during extraction: {e}")
        return {"error": "Gemini_API_Error"}
    except Exception as e:
        logging.error(f"An unexpected error occurred during extraction call: {e}", exc_info=True)
        return {"error": str(e)}