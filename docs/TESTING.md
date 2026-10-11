# Testing

```sh
backend-python/.venv/bin/python -m pytest backend-python/tests -q
mvn -f frontend-java/frontend-java/pom.xml clean test package
node --test scripts/tests/race-control-engine.test.js
```

The preserved application includes Race Control, track geometry, replay, strategy estimates, published weekend/Sprint predictions, news, CRUD and reports. Session refresh tests cover forced schedule acquisition, all public sessions, partial source failures, job deduplication and persistent metadata.
