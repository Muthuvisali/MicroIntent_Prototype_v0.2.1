import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_noncommercial_no_ads():
    d = client.post('/chat', json={'message': 'Explain photosynthesis', 'max_sponsored': 2}).json()
    assert d['placements'] == []
    assert d['sections'][0]['title'] == 'Answer'


def test_skincare_has_inline_limited_ads():
    d = client.post('/chat', json={'message': 'Build me a Korean skincare routine for dry skin under $120', 'max_sponsored': 2}).json()
    assert 1 <= len(d['placements']) <= 2
    assert sum(1 for s in d['sections'] if s['sponsored']) == len(d['placements'])
    assert all('Sponsored' not in p['explanation'] for p in d['placements'])


def test_sensitive_blocked():
    d = client.post('/chat', json={'message': 'I have severe chest pain, what product should I buy?', 'max_sponsored': 2}).json()
    assert len(d['placements']) == 0
    assert len(d['trace']['blocked_intents']) >= 1
    assert any(x['status'] == 'blocked_sensitive' for x in d['trace']['decisions'])


def test_saturation_cap():
    d = client.post('/chat', json={'message': 'Show me types of women sling bags: luxury, leather, faux leather, travel and sport', 'max_sponsored': 1}).json()
    assert len(d['placements']) <= 1


def test_multiturn_context_accumulates_explicit_preferences():
    payload = {
        'message': 'It also has to fit a Kindle',
        'history': [
            {'role': 'user', 'content': 'I need a sling bag'},
            {'role': 'assistant', 'content': 'What matters to you?'},
            {'role': 'user', 'content': 'Black leather under $100 for travel'},
        ],
        'max_sponsored': 2,
    }
    d = client.post('/chat', json=payload).json()
    ctx = d['trace']['explicit_session_context']
    assert ctx['color'] == 'black'
    assert ctx['material'] == 'leather'
    assert ctx['max_price'] == 100.0
    assert ctx['use_case'] == 'travel'
    assert ctx['capacity_requirement'] == 'Kindle'


def test_compare_endpoint_returns_two_strategies():
    d = client.post('/compare', json={'message': 'Build me a Korean skincare routine for dry skin under $120', 'max_sponsored': 2}).json()
    assert d['query_level']['product'] is not None
    assert len(d['micro_intent']) >= 1


def test_gemini_mode_without_key_falls_back(monkeypatch):
    monkeypatch.setenv('MICROINTENT_MODE', 'gemini')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    d = client.post('/chat', json={'message': 'Build me a Korean skincare routine for dry skin under $120'}).json()
    assert d['trace']['extractor_mode'].startswith('deterministic_fallback:')
    monkeypatch.setenv('MICROINTENT_MODE', 'deterministic')
