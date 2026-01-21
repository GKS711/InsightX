import os
import google.genai as genai
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables.")
        else:
            self.client = genai.Client(api_key=api_key)
            self.model = self.client.models

    def generate_content(self, prompt: str, generation_config: dict | None = None):
        """
        Generates content using the Gemini model based on the provided prompt.
        """
        if generation_config is None:
            generation_config = {}

        response = self.model.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            **generation_config
        )
        return response

    async def analyze_content(self, text_content: str):
        """
        Analyzes the scraped text content using Gemini.
        Returns a JSON structure compatible with the frontend.
        """
        if not text_content:
            return {"error": "No content to analyze"}

        prompt = f"""
        You are an expert business analyst. Analyze the following customer feedback text scraped from a website.
        
        Raw Text:
        {text_content[:15000]}  # Truncate to safe limit

        Task:
        1. Identify the platform (Google Maps, Facebook, or Other) based on the text.
        2. Analyze sentiment (Good/Bad) and extract key topics.
        3. Provide specific percentages (estimate) for top 3 Good and top 3 Bad user feedback topics.
        
        Output JSON exactly in this format (no markdown):
        {{
            "platform": "detected_platform",
            "total_reviews": "Estimate count based on text or N/A",
            "good": [
                {{"label": "Topic 1", "value": 30}},
                {{"label": "Topic 2", "value": 20}},
                {{"label": "Topic 3", "value": 10}}
            ],
            "bad": [
                {{"label": "Topic 1", "value": 40}},
                {{"label": "Topic 2", "value": 20}},
                {{"label": "Topic 3", "value": 10}}
            ]
        }}
        """
        
        try:
            response = self.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            return response.text
        except Exception as e:
            return {"error": str(e)}

    async def generate_reply(self, topic: str):
        prompt = f"Write a polite, professional response to a customer complaining about '{topic}'. Chinese Traditional."
        response = self.generate_content(prompt)
        return response.text

    async def generate_marketing(self, strengths: str):
         prompt = f"Write a Facebook post highlighting these strengths: {strengths}. Include emojis and hashtags. Chinese Traditional."
         response = self.generate_content(prompt)
         return response.text

    async def generate_root_cause_analysis(self, topic: str):
        prompt = f"""
        You are a business consultant. Analyze the root causes of the following issue reported by customers: '{topic}'.
        Provide a detailed analysis and suggest actionable improvements. Chinese Traditional.
        """
        response = self.generate_content(prompt)
        return response.text
    
    async def generate_weekly_plan(self, weaknesses: str):
        prompt = f"""
        You are a business strategist. Create a weekly action plan to address the following weaknesses in restaurant operations: {weaknesses}.
        The plan should include daily tasks and goals. Chinese Traditional.
        """
        response = self.generate_content(prompt)
        return response.text

    async def generate_training_script(self, issue: str):
        prompt = f"""
        You are a training expert. Create a training script for restaurant staff on the issue: '{issue}'.
        The script should be engaging and informative. Chinese Traditional.
        """
        response = self.generate_content(prompt)
        return response.text

    async def generate_internal_email(self, strengths: str, weaknesses: str):
        prompt = f"""
        You are an internal communications expert. Write a professional email to restaurant staff highlighting these strengths: {strengths}.
        Also address these weaknesses: {weaknesses}. Chinese Traditional.
        """
        response = self.generate_content(prompt)
        return response.text

    async def chat(self, user_message: str):
        # In a real app, we would pass history here. 
        # For simplicity, we just respond to the current message with system context.
        system_prompt = "You are an AI restaurant strategy consultant. Answer questions about restaurant operations, marketing, and analysis. Be professional and helpful. Chinese Traditional."
        
        # We can construct a combined prompt
        combined_prompt = f"{system_prompt}\n\nUser: {user_message}\nAI:"
        
        response = self.generate_content(combined_prompt)
        return response.text
