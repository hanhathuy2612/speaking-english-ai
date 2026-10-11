from app.core import config
from app.services.stt import unclear_reason


def result(text="I work on the payment service.", logprob=-0.4, no_speech=0.0, language="en"):
    return {"text": text, "avg_logprob": logprob, "no_speech": no_speech, "language": language}


def test_clear_english_passes():
    assert unclear_reason(result()) is None


def test_vietnamese_is_not_english():
    assert unclear_reason(result(text="Em làm Java được 5 năm rồi.")) == "not_english"
    assert unclear_reason(result(text="I work at the company for 5 years.", language="vi")) == "not_english"


def test_low_confidence():
    assert unclear_reason(result(logprob=config.STT_MIN_LOGPROB - 0.1)) == "low_confidence"
    assert unclear_reason(result(no_speech=config.STT_MAX_NO_SPEECH + 0.1)) == "low_confidence"
