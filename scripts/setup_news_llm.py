"""Pull the configured compact summarizer into a running local Ollama service."""
import json,os,time
import requests
import _bootstrap
from services.news_rewriter import NewsRewriter

def main():
    editor=NewsRewriter();editor.ensure_runtime()
    for attempt in range(20):
        try:
            requests.get(editor.base+'/api/tags',timeout=2).raise_for_status();break
        except requests.RequestException:
            if attempt==19:raise SystemExit('Start Ollama first (ollama serve), then run this script again.')
            time.sleep(.5)
    response=requests.post(editor.base+'/api/pull',json={'model':editor.model,'stream':True},stream=True,timeout=(5,900));response.raise_for_status();seen=set()
    for line in response.iter_lines():
        if not line:continue
        event=json.loads(line)
        if event.get('error'):raise RuntimeError(event['error'])
        status=event.get('status')
        if status not in seen:print(status,flush=True);seen.add(status)
    print(json.dumps(editor.status(),indent=2))
if __name__=='__main__':main()
