import os
from tavily import TavilyClient

try:
    from firecrawl import FirecrawlApp
except:
    FirecrawlApp = None

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

firecrawl = None

if FIRECRAWL_API_KEY and FirecrawlApp:
    firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

def tavily_search(query):

    try:

        response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5
        )

        return response.get("results", [])

    except Exception as e:

        return [{
            "title": "Search Error",
            "content": str(e),
            "url": ""
        }]

def crawl_page(url):

    if not firecrawl:
        return "Firecrawl unavailable."

    try:

        result = firecrawl.scrape_url(
            url=url,
            formats=["markdown"]
        )

        if isinstance(result, dict):

            data = result.get("markdown")

            if data:
                return data[:4000]

        return str(result)[:4000]

    except Exception as e:

        return f"Crawl error: {e}"

def research_web(query):

    results = tavily_search(query)

    final = []

    for r in results:

        title = r.get("title", "")
        url = r.get("url", "")
        content = r.get("content", "")

        crawled = ""

        if url:
            crawled = crawl_page(url)

        final.append({
            "title": title,
            "url": url,
            "summary": content,
            "crawl": crawled[:2000]
        })

    return final
