import os
import requests
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from upsonic import UpsonicClient, Task, AgentConfiguration, ObjectResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Upsonic client
client = UpsonicClient("localserver")
client.set_config("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID"))
client.set_config("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY"))
client.set_config("AWS_REGION", os.getenv("AWS_REGION"))

client.set_config("AZURE_OPENAI_ENDPOINT", os.getenv("AZURE_OPENAI_ENDPOINT"))
client.set_config("AZURE_OPENAI_API_VERSION", os.getenv("AZURE_OPENAI_API_VERSION"))
client.set_config("AZURE_OPENAI_API_KEY", os.getenv("AZURE_OPENAI_API_KEY"))

client.default_llm_model = "azure/gpt-4o"

# Define FastAPI app
app = FastAPI()

# Define Input Model
class SearchInput(BaseModel):
    keyword: str

# Define Response Format
class SearchResult(ObjectResponse):
    title: str
    link: str
    snippet: str

class SearchResponse(ObjectResponse):
    results: list[SearchResult]

# SerpAPI Tool for Web Search
@client.tool()
class SerpAPITool:
    def search(query: str) -> list:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="SerpAPI API Key not found!")

        url = "https://google.serper.dev/search"
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        payload = json.dumps({"q": query})
        
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            data = response.json()
            search_results = data.get("organic", [])
            
            return [
                SearchResult(
                    title=result.get("title", "No Title"),
                    link=result.get("link", "#"),
                    snippet=result.get("snippet", "No Description")
                )
                for result in search_results[:10]
            ]
        else:
            raise HTTPException(status_code=500, detail=f"SerpAPI Request Failed: {response.text}")

# Define Search Agent
search_agent = AgentConfiguration(
    job_title="Search Analyst",
    company_url="https://upsonic.ai",
    company_objective="Fetch and analyze the latest search results",
    reflection=True
)

@app.post("/search/")
async def perform_search(input_data: SearchInput):
    """Performs a web search using SerpAPI and returns the top results."""
    search_task = Task(
        description=f"Perform a web search for {input_data.keyword} and return the top results with titles, links, and snippets.",
        tools=[SerpAPITool],
        response_format=SearchResponse
    )
    
    client.agent(search_agent, search_task)
    search_data = search_task.response
    if not search_data:
        raise HTTPException(status_code=500, detail="Failed to fetch search results.")
    
    return {"keyword": input_data.keyword, "results": search_data.results}

# UI for search functionality
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Web Search</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin: 50px; }
            input { padding: 10px; margin: 10px; width: 300px; }
            button { padding: 10px; background: blue; color: white; border: none; cursor: pointer; }
            #results { margin-top: 20px; text-align: left; }
            footer { margin-top: 30px; font-size: 0.9em; color: #555; }
            footer a { color: #007BFF; text-decoration: none; }
            footer a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>AI Web Search</h1>
        <input type="text" id="keyword" placeholder="Enter a search keyword">
        <button onclick="fetchSearchResults()">Search</button>
        <div id="results"></div>
        <footer>
            Powered by <a href="https://upsonic.ai" target="_blank">UpsonicAI</a>
        </footer>
        <script>
            async function fetchSearchResults() {
                const keyword = document.getElementById('keyword').value;
                const response = await fetch('/search/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keyword })
                });

                const data = await response.json();
                let resultsHTML = "<h2>Results:</h2>";
                data.results.forEach(result => {
                    resultsHTML += `<p><strong>${result.title}</strong><br>${result.snippet}<br><a href="${result.link}" target="_blank">Read more</a></p>`;
                });
                document.getElementById('results').innerHTML = resultsHTML;
            }
        </script>
    </body>
    </html>
    """
