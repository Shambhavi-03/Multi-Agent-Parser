# your_project_name/core/shared_memory.py

import redis
import json
from typing import Dict, Any, Optional

# Redis connection: Assuming Redis is running on localhost:6379
# In a Dockerized setup, 'redis' would be the hostname.
_redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def set_transaction_data(transaction_id: str, data: Dict[str, Any]):
    """
    Stores or updates the entire transaction data object in Redis.
    """
    _redis_client.set(transaction_id, json.dumps(data))
    print(f"Shared Memory: Stored transaction {transaction_id}")

def get_transaction_data(transaction_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the entire transaction data object from Redis.
    """
    data = _redis_client.get(transaction_id)
    if data:
        return json.loads(data)
    return None

def update_transaction_data(transaction_id: str, new_data_fields: Dict[str, Any]):
    """
    Updates specific fields within an existing transaction data object in Redis.
    This reads, merges, then writes back.
    """
    current_data = get_transaction_data(transaction_id)
    if current_data:
        # Merge new fields into current data
        # Be careful with nested structures: this performs a shallow merge
        # For deep merges, consider a utility function or careful assignment.
        current_data.update(new_data_fields)
        set_transaction_data(transaction_id, current_data)
        print(f"Shared Memory: Updated transaction {transaction_id}")
        return True
    else:
        print(f"Shared Memory: Transaction {transaction_id} not found for update.")
        return False

# You might add more specific functions like:
# def append_to_trace(transaction_id: str, trace_entry: Dict[str, Any]):
#     data = get_transaction_data(transaction_id)
#     if data and "agent_decision_trace" in data:
#         data["agent_decision_trace"].append(trace_entry)
#         set_transaction_data(transaction_id, data)
#     else:
#         print(f"Error: Could not append trace for {transaction_id}")