"""Run one public Selenium news crawl and local-LLM rewrite cycle."""
import json
import _bootstrap
from database.migrations import migrate
from services.news_service import NewsService
if __name__=='__main__':
    migrate();print(json.dumps(NewsService().crawl(),indent=2,ensure_ascii=False))
