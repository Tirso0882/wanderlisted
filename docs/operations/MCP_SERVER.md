# Wanderlisted MCP Server — Setup & Configuration

## What this does

Exposes Wanderlisted's 16 travel tools as an MCP server so external AI agents can use them:

```
Claude Desktop / Cursor / VS Code Copilot
    │
    ├── MCP protocol (JSON-RPC over stdio)
    │
    ▼
wanderlisted-travel MCP Server
    │
    ├── search_flights        (Amadeus)
    ├── search_hotels         (Amadeus)
    ├── get_weather           (OpenWeatherMap)
    ├── calculate_budget      (local)
    ├── search_destination_guides (Pinecone RAG)
    ├── search_places_nearby  (Google Maps)
    ├── search_places_text    (Google Maps)
    ├── get_directions        (Google Maps)
    ├── get_distance_matrix   (Google Maps)
    ├── get_timezone          (Google Maps)
    ├── optimize_day_route    (Google Maps)
    ├── search_web            (Tavily)
    ├── search_hidden_gems    (Tavily)
    ├── get_safety_info       (REST Countries)
    ├── convert_currency      (ExchangeRate API)
    └── lookup_iata_code      (local CSV)
```

## Install dependency

```bash
pip install mcp
```

Or add to `requirements.txt`:
```
mcp>=1.0.0
```

## Run standalone

```bash
# From project root, with .env loaded
python -m src.mcp_server
```

## Configure in Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "wanderlisted-travel": {
      "command": "/Users/Tirso.Gomez/Documents/projects/wanderlisted/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/Users/Tirso.Gomez/Documents/projects/wanderlisted",
      "env": {
        "AMADEUS_API_KEY": "your-key",
        "AMADEUS_API_SECRET": "your-secret",
        "AMADEUS_BASE_URL": "https://api.amadeus.com",
        "GOOGLE_MAPS_API_KEY": "your-key",
        "OPENWEATHER_API_KEY": "your-key",
        "PINECONE_API_KEY": "your-key",
        "PINECONE_INDEX_NAME": "wanderlisted",
        "TAVILY_API_KEY": "your-key",
        "AZURE_OPENAI_API_KEY": "your-key"
      }
    }
  }
}
```

## Configure in VS Code / Copilot

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "wanderlisted-travel": {
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "${workspaceFolder}",
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

## Configure in Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "wanderlisted-travel": {
      "command": ".venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/Users/Tirso.Gomez/Documents/projects/wanderlisted",
      "envFile": ".env"
    }
  }
}
```

## What users can do

Once connected, a user in Claude Desktop can say:

> "Find me flights from Seattle to Tokyo in July, then search for budget hotels
> in Shinjuku, check the weather, and calculate a 7-day budget for 2 travelers."

Claude will call `lookup_iata_code`, `search_flights`, `search_hotels`,
`get_weather`, and `calculate_budget` automatically — using YOUR tools,
YOUR API keys, YOUR Pinecone knowledge base.

## Architecture note

This MCP server is a **distribution layer only**. Your internal LangGraph
agents still call `@tool` functions directly — no MCP overhead for your
own pipeline. This server exists so EXTERNAL agents can use your tools.
