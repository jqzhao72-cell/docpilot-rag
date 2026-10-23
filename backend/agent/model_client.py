"""Provider boundary: minimal OpenAI-compatible Chat Completions protocol."""
import os

from openai import OpenAI, APITimeoutError


class ModelClient:
    def __init__(self, client=None):
        self.model = os.getenv('AGENT_MODEL') or os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        key = os.getenv('AGENT_API_KEY') or os.getenv('DEEPSEEK_API_KEY')
        if client is None and not key:
            raise EnvironmentError('Agent model credentials are not configured')
        self.client = client or OpenAI(api_key=key,
            base_url=os.getenv('AGENT_BASE_URL') or os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
            max_retries=0)

    def complete(self, messages, tools, allow_tools, timeout):
        # Do not assume providers support strict, parallel_tool_calls, reasoning_effort,
        # temperature or response_format. Optional capabilities belong in this adapter.
        try:
            response = self.client.with_options(timeout=timeout).chat.completions.create(
                model=self.model, messages=messages, tools=tools,
                tool_choice='auto' if allow_tools else 'none')
        except APITimeoutError:
            raise TimeoutError() from None
        if not response.choices:
            raise ValueError('Empty model choices')
        message = response.choices[0].message
        return {'message': message.model_dump(exclude_none=True,
                    include={'role', 'content', 'tool_calls'}),
                'finish_reason': response.choices[0].finish_reason,
                'usage': response.usage.model_dump() if response.usage else {}}

    def close(self):
        self.client.close()
