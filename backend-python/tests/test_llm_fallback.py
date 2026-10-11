from services.llm_service import LLMExplanationService

def test_disabled_llm_makes_no_calls(monkeypatch):
    class Never:
        @property
        def responses(self):raise AssertionError('Network must not run')
    monkeypatch.setenv('LLM_ENABLED','false')
    data={'predictions':[{'driver_name':'Example Driver','win_probability':.3}]}
    result=LLMExplanationService().explain(data,client=Never())
    assert result['source']=='template';assert '30.0%' in result['text'];assert data['predictions'][0]['win_probability']==.3

def test_unavailable_llm_falls_back(monkeypatch):
    monkeypatch.setenv('LLM_ENABLED','true');monkeypatch.setenv('LLM_CACHE_ENABLED','false')
    class Broken:
        @property
        def responses(self):raise TimeoutError()
    assert LLMExplanationService().explain({'predictions':[]},client=Broken())['source']=='template'

def test_missing_key_works(monkeypatch):
    monkeypatch.setenv('LLM_ENABLED','true');monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert LLMExplanationService().explain({})['source']=='template'
