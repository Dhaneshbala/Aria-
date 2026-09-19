"""Feature 6 slice 1: citation correctness pinned (hermetic)."""
from services.citation_service import CitationService


def test_hallucinated_citations_dropped():
    svc = CitationService()
    svc.register_sources(web_results=[{"title": "T", "snippet": "S", "url": "https://x"}])
    _, cites = svc.parse_citations("Fact [1] and invented [99].")
    assert [c.index for c in cites] == [1]


def test_duplicate_citations_deduped():
    svc = CitationService()
    svc.register_sources(web_results=[{"title": "T", "snippet": "S", "url": "https://x"}])
    _, cites = svc.parse_citations("[1] again [1].")
    assert len(cites) == 1


def test_no_sources_no_citations():
    svc = CitationService()
    svc.register_sources()
    _, cites = svc.parse_citations("Nothing [1] here.")
    assert cites == []
