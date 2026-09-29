import os

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()


class DeepSeekLLM:


    def __init__(self):

        self.client = OpenAI(
            api_key=os.getenv(
                "DEEPSEEK_API_KEY"
            ),
            base_url="https://api.deepseek.com"
        )


    def generate(self, prompt):

        response = self.client.chat.completions.create(

            model="deepseek-chat",

            messages=[

                {
                    "role": "system",
                    "content":
                    "你是一个企业知识库助手，请根据提供资料回答问题。"
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.2
        )


        return response.choices[0].message.content