from backend.pedagogy import SYSTEM_PROMPT

def test_pedagogical_constraints():
    assert 'unicornios' in SYSTEM_PROMPT
    assert 'MRU' in SYSTEM_PROMPT
    assert 'datos personales' in SYSTEM_PROMPT
