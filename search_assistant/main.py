import yaml
import os
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
from cerebras.cloud.sdk import Cerebras

app = FastAPI(
    title="LLM Response Service",
    description="A service that generates summary responses using LLM based on relevant text windows",
    version="1.0.0"
)

# Load configuration
def load_config():
    """Load configuration from YAML file"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

config = load_config()

client = Cerebras(
    api_key=config['llm']['api_key'],
)

class LLMRequest(BaseModel):
    most_relevant_windows: List[str]
    query: str

class LLMResponse(BaseModel):
    response: str

@app.post("/generate_summary", response_model=LLMResponse)
async def generate_summary(request: LLMRequest):
    """
    Generate a summary response to a query based on relevant text windows using LLM.
    
    Args:
        request: Contains most_relevant_windows (List[str]) and query (str)
    
    Returns:
        LLMResponse: Contains the generated summary response
    """
    try:
        context = "\n\n".join([f"Text Window {i+1}:\n{window[:4000]}" 
                              for i, window in enumerate(request.most_relevant_windows)])
        system_prompt = config["system_prompt"].format(
            text_windows=context
        )
        user_prompt = config["user_prompt"].format(
            query=request.query
        )

        # Call the LLM API
        response = client.chat.completions.create(
            model=config["llm"]["model"],  # Using a general model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        # Extract the response text
        summary_response = response.choices[0].message.content
        end_reasoning = summary_response.find("</think>")
        if end_reasoning != -1:
            summary_response = summary_response[end_reasoning+len("</think>"):]
        
        return LLMResponse(response=summary_response.strip())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "LLM Response Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1984)
