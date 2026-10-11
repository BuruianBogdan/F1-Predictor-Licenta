# Optional LLM explanations

The language model narrates already calculated predictions and confirmed results. It neither selects winners nor produces probabilities, features, labels, odds or model metrics. UI numerical cards always come from the quantitative engine.

Install `backend-python/requirements-llm.txt`, then configure locally:

```dotenv
LLM_ENABLED=true
OPENAI_API_KEY=your-local-key
OPENAI_MODEL=your-accessible-model-id
LLM_TIMEOUT_SECONDS=20
LLM_CACHE_ENABLED=true
```

No model name is hardcoded. Use a model supported by the account. The official Python SDK calls `client.responses.create` with `store=False`, bounded output, a timeout and one retry. Only the supplied application facts are sent as input; provider strings are treated as data, and the prompt prohibits inventing or altering probabilities. See the [official Python API reference](https://developers.openai.com/api/reference/python).

POST `/explanations/prediction/{run_id}?lang=ro` explains a saved forecast. POST `/explanations/race/{race_id}?lang=ro` generates a recap. English is the default. The race detail page provides an on-demand recap button. Prediction explanations are available through the API; observed explanation factors are always present in the prediction UI.

The cache key hashes payload, language, narrative kind and model. No dashboard request calls the API. Disabled integration, missing key/model, unavailable SDK, timeout, empty response or API failure returns deterministic RO/EN text and its source/reason.

Verification: disabled, missing-credential and simulated failure paths passed; the installed SDK imports successfully. **No live API call was made because OPENAI_API_KEY was not configured.** A generated narrative may still be inaccurate; it is explicitly labelled and never changes the persisted probabilities. Local `.env` and secrets are ignored by version control.
