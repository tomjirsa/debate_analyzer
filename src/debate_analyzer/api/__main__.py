"""Run the web app: python -m debate_analyzer.api."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "debate_analyzer.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
