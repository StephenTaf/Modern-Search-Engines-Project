import CrawlerHelpers

import pytest
import time

import CrawlerHelpers
from CrawlerHelpers import errorDomain

@pytest.fixture(autouse=True)
def reset_globals():
    # Reset global state before each test
    CrawlerHelpers.responseHttpCodes.clear()
    CrawlerHelpers.urlFrontier.clear()
    yield

class CallRecorder:
    def __init__(self):
        self.calls = []
    def record(self, *args):
        self.calls.append(args)

@pytest.mark.parametrize("code, delays_calls, move_calls", [
    # First two calls for code 400: exponentialDelay; third: two moveAndDel calls
    (400, [(5, 'dom')]*2, [('dom', True)]),
])
def test_code_400_behavior(monkeypatch, code, delays_calls, move_calls):
    domain = 'dom'
    headers = {"status_code": code}
    # Prepare frontier
    CrawlerHelpers.urlFrontier[domain] = {"crawl-delay": None}
    # Stub retry
    monkeypatch.setattr(CrawlerHelpers, 'retry', lambda h: None)
    # Recorders
    exp = CallRecorder()
    mv = CallRecorder()
    monkeypatch.setattr(CrawlerHelpers, 'exponentialDelay', exp.record)
    monkeypatch.setattr(CrawlerHelpers, 'moveAndDel', mv.record)
    # Call three times
    for _ in range(3):
        errorDomain(domain, headers, 5)
    # Check calls
    assert exp.calls == delays_calls
    assert mv.calls == move_calls

@pytest.mark.parametrize("code, first_exp, second_move", [
    # Code 401 (400<code<500, code!=429): first exp, second move
    (401, True, True),
])
def test_code_4xx_non429(monkeypatch, code, first_exp, second_move):
    domain = 'd'
    headers = {"status_code": code}
    CrawlerHelpers.urlFrontier[domain] = {"crawl-delay": None}
    monkeypatch.setattr(CrawlerHelpers, 'retry', lambda h: None)
    exp = CallRecorder()
    mv = CallRecorder()
    monkeypatch.setattr(CrawlerHelpers, 'exponentialDelay', exp.record)
    monkeypatch.setattr(CrawlerHelpers, 'moveAndDel', mv.record)

    # First call
    errorDomain(domain, headers, 3)
    assert (3, domain) in exp.calls if first_exp else True
    # Second call
    errorDomain(domain, headers, 3)
    assert mv.calls and mv.calls[0] == (domain, True)

@pytest.mark.parametrize("retry_val, should_exp", [
    (None, True),
    (10, False),
])
def test_code_429_behavior(monkeypatch, retry_val, should_exp):
    domain = 'x'
    headers = {"status_code": 429}
    CrawlerHelpers.urlFrontier[domain] = {"crawl-delay": None}
    monkeypatch.setattr(CrawlerHelpers, 'retry', lambda h: retry_val)
    exp = CallRecorder()
    mv = CallRecorder()
    monkeypatch.setattr(CrawlerHelpers, 'exponentialDelay', exp.record)
    monkeypatch.setattr(CrawlerHelpers, 'moveAndDel', mv.record)

    # Single call
    errorDomain(domain, headers, 7)
    assert (7, domain) in exp.calls if should_exp else not exp.calls

def test_code_429_threshold(monkeypatch):
    # On 10th call moveAndDel
    domain = 'y'
    headers = {"status_code": 429}
    CrawlerHelpers.urlFrontier[domain] = {"crawl-delay": None}
    monkeypatch.setattr(CrawlerHelpers, 'retry', lambda h: None)
    exp = CallRecorder()
    mv = CallRecorder()
    monkeypatch.setattr(CrawlerHelpers, 'exponentialDelay', exp.record)
    monkeypatch.setattr(CrawlerHelpers, 'moveAndDel', mv.record)

    for i in range(10):
        errorDomain(domain, headers, 1)
    # Should have a move call at 10th invocation
    assert (domain, True) in mv.calls

@pytest.mark.parametrize("code, retry_val, exp_count, move_count", [
    # Code 503 with retry=>None: all exp until 5th move twice
    (503, None, 5, 1),
    # Code 500 (in 499<code<507) behaves similarly
    (500, None, 5, 1),
    # Code 599 (==599)
    (599, None, 5, 1),
])
def test_5xx_behaviors(monkeypatch, code, retry_val, exp_count, move_count):
    domain = 'z'
    headers = {"status_code": code}
    CrawlerHelpers.urlFrontier[domain] = {"crawl-delay": None}
    monkeypatch.setattr(CrawlerHelpers, 'retry', lambda h: retry_val)
    exp = CallRecorder()
    mv = CallRecorder()
    monkeypatch.setattr(CrawlerHelpers, 'exponentialDelay', exp.record)
    monkeypatch.setattr(CrawlerHelpers, 'moveAndDel', mv.record)

    # Call 5 times
    for _ in range(5):
        errorDomain(domain, headers, 2)
    assert len(exp.calls) == exp_count
    # Two move calls at threshold
    assert mv.calls.count((domain, True)) == move_count

@pytest.mark.parametrize("code", [507, 508, 509])
def test_506_to_510_behavior(monkeypatch, code):
    domain = 'a'
    headers = {"status_code": code}
    CrawlerHelpers.urlFrontier[domain] = {"crawl-delay": None}
    monkeypatch.setattr(CrawlerHelpers, 'retry', lambda h: None)
    exp = CallRecorder()
    mv = CallRecorder()
    monkeypatch.setattr(CrawlerHelpers, 'exponentialDelay', exp.record)
    monkeypatch.setattr(CrawlerHelpers, 'moveAndDel', mv.record)

    # First two calls assign frontier-delay
    for _ in range(2):
        errorDomain(domain, headers, 4)
        # No exponential
        assert not exp.calls
        # Frontier set
        assert CrawlerHelpers.urlFrontier[domain]["crawl-delay"] == 3600
    # Third call: move twice
    errorDomain(domain, headers, 4)
    assert mv.calls and mv.calls[-1] == (domain, True)

@pytest.mark.parametrize("code", [200, 300, 302])
def test_else_branch(monkeypatch, code):
    domain = 'b'
    headers = {"status_code": code}
    CrawlerHelpers.urlFrontier[domain] = {"crawl-delay": None}
    monkeypatch.setattr(CrawlerHelpers, 'retry', lambda h: None)
    exp = CallRecorder()
    mv = CallRecorder()
    monkeypatch.setattr(CrawlerHelpers, 'exponentialDelay', exp.record)
    monkeypatch.setattr(CrawlerHelpers, 'moveAndDel', mv.record)

    # Two calls: nothing
    errorDomain(domain, headers, 9)
    errorDomain(domain, headers, 9)
    assert not exp.calls and not mv.calls
    # Third: move twice (first in codeblock? then else)
    errorDomain(domain, headers, 9)
    assert mv.calls and mv.calls[-1] == (domain, True)



