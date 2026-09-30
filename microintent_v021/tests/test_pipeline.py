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


def test_political_context_blocked():
    d = client.post('/chat', json={'message': 'Which candidate should I vote for?', 'max_sponsored': 2}).json()
    assert d['placements'] == []
    assert any(x['status'] == 'blocked_sensitive' for x in d['trace']['decisions'])


def test_japan_trip_decomposes_into_travel_micro_intents():
    d = client.post('/chat', json={'message': 'Plan a 7-day Japan trip', 'max_sponsored': 2}).json()
    labels = [m['label'] for m in d['trace']['micro_intents']]
    assert labels == ['flight', 'hotel', 'rail pass', 'activities', 'mobile data', 'dining']
    assert 1 <= len(d['placements']) <= 2
    assert all(p['product']['product_id'].startswith('trip') for p in d['placements'])


def test_japan_history_is_not_monetized():
    d = client.post('/chat', json={'message': 'What is the history of Japanese rail?', 'max_sponsored': 2}).json()
    assert d['placements'] == []


SKINCARE = 'Build me a Korean skincare routine for dry skin under $120'


def test_components_are_scored_independently():
    d = client.post('/chat', json={'message': SKINCARE}).json()
    scores = {m['label']: m['commercial_score'] for m in d['trace']['micro_intents']}
    assert len(set(scores.values())) > 1
    assert scores['sunscreen'] > scores['toner']


def test_rejections_carry_reasons_and_diversity_rule_fires():
    d = client.post('/chat', json={'message': SKINCARE, 'max_sponsored': 3}).json()
    statuses = {x['label']: x['status'] for x in d['trace']['decisions']}
    assert sum(s == 'selected' for s in statuses.values()) == 3
    assert 'eligible_not_selected' not in statuses.values()
    # Barrier Cream is from Hanok Glow, which already holds the oil-cleanser slot.
    assert statuses['moisturizer'] == 'not_selected_diversity'
    advertisers = [p['product']['advertiser'] for p in d['placements']]
    assert len(advertisers) == len(set(advertisers))


def test_organic_options_are_separate_from_sponsored():
    d = client.post('/chat', json={'message': SKINCARE}).json()
    for s in d['sections']:
        assert s['organic'], s['title']
        if s['sponsored']:
            assert s['sponsored']['product']['product_id'] not in {o['product_id'] for o in s['organic']}


def test_sensitive_context_lists_no_products():
    d = client.post('/chat', json={'message': 'I have severe chest pain. What should I buy?'}).json()
    assert all(not s['organic'] for s in d['sections'])


def test_ad_system_failure_still_returns_answer(monkeypatch):
    import app.services.pipeline as pipeline

    def boom(*a, **k):
        raise RuntimeError('ranking service down')

    monkeypatch.setattr(pipeline, 'rank', boom)
    r = client.post('/chat', json={'message': SKINCARE})
    assert r.status_code == 200
    d = r.json()
    assert d['placements'] == []
    assert d['trace']['monetization_status'] == 'failed:RuntimeError'
    assert len(d['sections']) == 7 and d['answer']
