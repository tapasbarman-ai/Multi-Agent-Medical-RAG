import os
from langchain_tavily import TavilySearch


def push_event(state, event_type, data):
    """Helper to push events to the Flask SSE queue if present."""
    q = state.get("metadata", {}).get("event_queue")
    if q and hasattr(q, "put"):
        q.put({"type": event_type, **data})

def websearch_tool(state):
    query = state["query"]
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        print("❌ WebSearch: TAVILY_API_KEY not found")
        return {
            **state,
            "results": ["Tavily API key not configured."]
        }

    tavily = TavilySearch(tavily_api_key=api_key)

    print(f"🔍 WebSearch: Searching for '{query}'")
    push_event(state, "status", {"message": "🌐 WebSearch: Querying Tavily for latest medical news and updates..."})

    try:
        raw_result = tavily.run(query)

        # Debug: Print the raw structure
        print(f"🔍 Debug - Raw result type: {type(raw_result)}")
        print(f"🔍 Debug - Raw result: {raw_result[:500] if isinstance(raw_result, str) else raw_result}")

        # Handle different response formats
        formatted_results = []

        # Case 1: If it's already a formatted string
        if isinstance(raw_result, str):
            formatted_results = [raw_result]

        # Case 2: If it's a list of dicts (common Tavily format)
        elif isinstance(raw_result, list):
            for item in raw_result[:5]:
                if isinstance(item, dict):
                    # Check if it has nested 'results' key
                    if 'results' in item:
                        for result in item['results'][:5]:
                            title = result.get('title', 'No title')
                            content = result.get('content', 'No content')
                            url = result.get('url', '')
                            formatted_results.append(f"**{title}**\n{content}\nSource: {url}")
                    # Or if item itself is a result
                    else:
                        title = item.get('title', 'No title')
                        content = item.get('content', 'No content')
                        url = item.get('url', '')
                        formatted_results.append(f"**{title}**\n{content}\nSource: {url}")

        # Case 3: If it's a dict
        elif isinstance(raw_result, dict):
            if 'results' in raw_result:
                for result in raw_result['results'][:5]:
                    title = result.get('title', 'No title')
                    content = result.get('content', 'No content')
                    url = result.get('url', '')
                    formatted_results.append(f"**{title}**\n{content}\nSource: {url}")
            elif 'answer' in raw_result:
                formatted_results = [raw_result['answer']]

        if formatted_results:
            print(f"✅ WebSearch: Found {len(formatted_results)} results")
            push_event(state, "status", {"message": f"🌐 WebSearch: Retrieved {len(formatted_results)} recent news/guideline articles."})
            return {
                **state,
                "results": formatted_results
            }
        else:
            print("⚠️ WebSearch: No results found in response")
            return {
                **state,
                "results": ["No recent medical news found. Try rephrasing your query."]
            }

    except Exception as e:
        print(f"❌ WebSearch Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "results": [f"Error searching: {str(e)}"]
        }