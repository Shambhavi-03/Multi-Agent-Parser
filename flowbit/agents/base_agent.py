# agents/base_agent.py (optional, for common methods)
class BaseAgent:
    def __init__(self, memory):
        self.memory = memory
        self.llm = self._initialize_llm() # Common LLM setup

    def _initialize_llm(self):
        # Initialize your chosen LLM (OpenAI, Gemini, etc.)
        # Example with OpenAI:
        # from openai import OpenAI
        # return OpenAI(api_key="YOUR_API_KEY")
        pass

    def process(self, data, record_id):
        raise NotImplementedError