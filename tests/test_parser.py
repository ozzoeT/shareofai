from core.parser import parse_json_response, validate_response


def test_parse_clean_json():
    raw = '{"answer": "a", "decision": "d", "preferred_brand": "X", ' \
          '"confidence": 80, "confidence_rationale": "r", "sources": ["s"]}'
    parsed, err = parse_json_response(raw)
    assert err is None
    assert parsed["preferred_brand"] == "X"


def test_parse_strips_markdown_fences():
    raw = '```json\n{"a": 1}\n```'
    parsed, err = parse_json_response(raw)
    assert err is None
    assert parsed == {"a": 1}


def test_parse_empty_response():
    parsed, err = parse_json_response("")
    assert parsed is None
    assert err is not None


def test_parse_extracts_json_with_preamble():
    raw = 'Sure, here it is:\n{"a": 1}\nHope this helps!'
    parsed, err = parse_json_response(raw)
    assert err is None
    assert parsed == {"a": 1}


def _base_obj(**overrides):
    obj = {
        "answer": "a",
        "decision": "d",
        "preferred_brand": "X",
        "confidence": 80,
        "confidence_rationale": "r",
        "sources": ["s"],
    }
    obj.update(overrides)
    return obj


def test_validate_response_ok():
    ok, err = validate_response(_base_obj())
    assert ok is True
    assert err is None


def test_validate_response_missing_keys():
    obj = _base_obj()
    del obj["decision"]
    ok, err = validate_response(obj)
    assert ok is False
    assert "decision" in err


def test_validate_response_confidence_out_of_range():
    ok, err = validate_response(_base_obj(confidence=150))
    assert ok is False


def test_validate_response_sources_not_list():
    ok, err = validate_response(_base_obj(sources="not-a-list"))
    assert ok is False


def test_validate_response_with_valid_source_evaluation():
    obj = _base_obj(source_evaluation={
        "source_strength": "strong",
        "source_strength_reason": "good data",
        "tone_detected": "technical",
        "tone_alignment": "aligned",
        "decisive_factor": "clinical studies",
    })
    ok, err = validate_response(obj)
    assert ok is True


def test_validate_response_invalid_source_strength():
    obj = _base_obj(source_evaluation={"source_strength": "very strong"})
    ok, err = validate_response(obj)
    assert ok is False


def test_validate_response_invalid_tone_alignment():
    obj = _base_obj(source_evaluation={"tone_alignment": "perfect"})
    ok, err = validate_response(obj)
    assert ok is False


def test_validate_response_source_evaluation_field_wrong_type():
    obj = _base_obj(source_evaluation={"decisive_factor": ["not", "a", "string"]})
    ok, err = validate_response(obj)
    assert ok is False
