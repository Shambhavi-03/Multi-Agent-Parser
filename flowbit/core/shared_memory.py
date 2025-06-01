# your_project_name/core/shared_memory.py

import redis
import json
import os # Import os to access environment variables
import logging # Import logging for better output management
from typing import Dict, Any, Optional

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Redis Connection Initialization ---
# Read Redis configuration from environment variables
# Defaults are provided for local development if env vars are not set
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379)) # Convert port to integer
REDIS_DB = int(os.getenv("REDIS_DB", 0)) # Convert DB to integer

_redis_client = None # Initialize as None

try:
    # Attempt to connect to Redis
    _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    _redis_client.ping() # Test the connection
    logging.info(f"Shared Memory: Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
except redis.exceptions.ConnectionError as e:
    logging.error(f"Shared Memory: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. "
                  f"Please ensure the Redis server is running and accessible. Error: {e}")
    # It's critical to raise an exception here or handle gracefully,
    # as the application cannot function without shared memory.
    raise ConnectionError(f"Failed to connect to Redis: {e}")
except ValueError as e:
    logging.error(f"Shared Memory: Invalid Redis PORT or DB environment variable. Error: {e}")
    raise ValueError(f"Invalid Redis configuration: {e}")
except Exception as e:
    logging.error(f"Shared Memory: An unexpected error occurred during Redis connection: {e}")
    raise Exception(f"Unexpected Redis connection error: {e}")


def set_transaction_data(transaction_id: str, data: Dict[str, Any]):
    """
    Stores or updates the entire transaction data object in Redis.
    """
    if _redis_client:
        _redis_client.set(transaction_id, json.dumps(data))
        logging.info(f"Shared Memory: Stored transaction {transaction_id}")
    else:
        logging.error(f"Shared Memory: Redis client not initialized. Cannot store transaction {transaction_id}.")

def get_transaction_data(transaction_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the entire transaction data object from Redis.
    """
    if _redis_client:
        data = _redis_client.get(transaction_id)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                logging.error(f"Shared Memory: Failed to decode JSON for transaction {transaction_id}. Error: {e}")
                return None
        return None
    else:
        logging.error(f"Shared Memory: Redis client not initialized. Cannot retrieve transaction {transaction_id}.")
        return None

def update_transaction_data(transaction_id: str, new_data_fields: Dict[str, Any]):
    """
    Updates specific fields within an existing transaction data object in Redis.
    This reads, merges, then writes back.
    """
    if _redis_client:
        current_data = get_transaction_data(transaction_id)
        if current_data:
            # Merge new fields into current data
            # This performs a shallow merge. For deep merges of nested dicts,
            # a more complex merge logic would be needed.
            current_data.update(new_data_fields)
            set_transaction_data(transaction_id, current_data)
            logging.info(f"Shared Memory: Updated transaction {transaction_id}")
            return True
        else:
            logging.warning(f"Shared Memory: Transaction {transaction_id} not found for update.")
            return False
    else:
        logging.error(f"Shared Memory: Redis client not initialized. Cannot update transaction {transaction_id}.")
        return False

# You might add more specific functions like:
# def append_to_trace(transaction_id: str, trace_entry: Dict[str, Any]):
#     if _redis_client:
#         data = get_transaction_data(transaction_id)
#         if data and "agent_decision_trace" in data:
#             data["agent_decision_trace"].append(trace_entry)
#             set_transaction_data(transaction_id, data)
#         else:
#             logging.error(f"Error: Could not append trace for {transaction_id} (data or trace field missing).")
#     else:
#         logging.error(f"Shared Memory: Redis client not initialized. Cannot append trace for {transaction_id}.")