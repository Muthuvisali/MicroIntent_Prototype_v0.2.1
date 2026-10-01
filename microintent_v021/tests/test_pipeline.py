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


def test_llm_labels_map_to_catalog_categories():
    from app.services.intents import canonical_label
    assert canonical_label('Double cleanse: cleansing oil') == 'oil cleanser'
    assert canonical_label('Vegan leather sling for commuting') == 'faux leather sling bag'
    assert canonical_label('Leather sling bag') == 'leather sling bag'
    assert canonical_label('JR Pass') == 'rail pass'
    assert canonical_label('eye cream') == 'eye cream'


def test_gemini_free_form_labels_reach_inventory(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    from app.models import LLMIntentExtraction, LLMIntentItem

    payload = LLMIntentExtraction(parent_intent='10-step skincare routine', items=[
        LLMIntentItem(label='Cleansing oil (first cleanse)', commercial_score=0.8, guidance='Look for one that emulsifies.'),
        LLMIntentItem(label='oil cleanser', commercial_score=0.9),
        LLMIntentItem(label='SPF 50 sunscreen', commercial_score=0.85),
        LLMIntentItem(label='Eye cream', commercial_score=0.6, guidance='Pick a gentle, fragrance-free formula.'),
    ])

    class FakeClient:
        def __init__(self, **kw):
            self.models = SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(parsed=payload))

    monkeypatch.setattr(genai, 'Client', FakeClient)
    monkeypatch.setenv('MICROINTENT_MODE', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    d = client.post('/chat', json={'message': 'give me a 10 step skincare routine'}).json()
    assert d['trace']['extractor_mode'] == 'gemini'
    labels = [m['label'] for m in d['trace']['micro_intents']]
    assert labels == ['oil cleanser', 'sunscreen', 'eye cream']
    assert d['trace']['micro_intents'][0]['commercial_score'] == 0.9
    assert len(d['placements']) >= 1
    eye = next(s for s in d['sections'] if s['title'] == 'Eye Cream')
    assert eye['body'] == 'Pick a gentle, fragrance-free formula.'


def test_answer_does_not_invent_skin_type():
    d = client.post('/chat', json={'message': 'give me a 10 step skincare routine'}).json()
    assert 'dry skin' not in d['answer'].lower()
    d = client.post('/chat', json={'message': 'skincare routine for oily skin'}).json()
    assert 'oily skin' in d['answer'].lower()


def test_informational_skincare_question_gets_no_routine_answer():
    d = client.post('/chat', json={'message': 'Tell me about the history of Korean skincare'}).json()
    assert 'routine' not in d['answer'].lower()
    assert d['placements'] == []


SKINCARE_HISTORY = [
    {'role': 'user', 'content': 'give me a 10 step skincare routine'},
    {'role': 'assistant', 'content': '...'},
    {'role': 'user', 'content': 'korean skincare'},
    {'role': 'assistant', 'content': '...'},
]


def test_topic_change_does_not_inherit_previous_topic():
    d = client.post('/chat', json={'message': 'what is photosynthesis', 'history': SKINCARE_HISTORY}).json()
    assert [m['label'] for m in d['trace']['micro_intents']] == ['general information']
    assert d['placements'] == []
    assert d['trace']['commercial_intent_band'] in ('none', 'low')


def test_follow_up_without_topic_still_inherits_topic():
    d = client.post('/chat', json={'message': 'under $40 please', 'history': SKINCARE_HISTORY}).json()
    assert 'sunscreen' in [m['label'] for m in d['trace']['micro_intents']]
    assert d['trace']['explicit_session_context']['max_price'] == 40.0


def test_new_topic_drops_old_preferences():
    hist = [{'role': 'user', 'content': 'Black leather sling bag under $100'}, {'role': 'assistant', 'content': '...'}]
    d = client.post('/chat', json={'message': 'Plan a 7-day Japan trip', 'history': hist}).json()
    assert d['trace']['micro_intents'][0]['label'] == 'flight'
    assert 'material' not in d['trace']['explicit_session_context']


def test_earlier_sensitive_context_still_blocks_vague_follow_up():
    hist = [{'role': 'user', 'content': 'I have severe chest pain'}, {'role': 'assistant', 'content': '...'}]
    d = client.post('/chat', json={'message': 'what should I buy?', 'history': hist}).json()
    assert d['placements'] == []
    assert any(x['status'] == 'blocked_sensitive' for x in d['trace']['decisions'])
