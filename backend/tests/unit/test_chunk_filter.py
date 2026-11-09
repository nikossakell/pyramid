"""Απόφαση 9: φίλτρα ποιότητας κομματιών. Συνθετικά κείμενα, στο ύφος των γνωμοδοτήσεων EFSA."""
from ai_pipeline.rag import chunk_filter
from ai_pipeline.rag.chunk_filter import classify, filter_chunks
from ai_pipeline.rag.chunking import Chunk

PROSE = ("Iron is an essential component of haemoglobin, which carries oxygen in the blood, and of myoglobin "
         "in muscle. Foods that contain relatively high concentrations of iron include meat, fish, legumes, "
         "whole grain cereals and dark green leafy vegetables. Absorption of non-haem iron is enhanced by "
         "vitamin C and reduced by phytate and polyphenols. Children need iron for growth and for the "
         "development of the brain, and adolescents need more iron during rapid growth.")


def ch(text, section="", n=1):
    return Chunk(chunk_id=f"src:{n:04d}", source_id="src", title="T", organization="O", version="v1", language="en",
                 section=section, page_start=1, page_end=1, text=text, text_sha256="x", approved=True)


# ---------- ένα test ανά κανόνα ----------

def test_toc_by_dot_leaders():
    text = ("TABLE OF CONTENTS Abstract ........................ 1 Summary ........................ 3 "
            "1. Introduction ........................ 7 2. Dietary sources ........................ 12")
    assert classify(ch(text)) == "toc"
    assert classify(ch("Abstract …… 1 Summary …… 3 Introduction …… 7")) == "toc"


def test_toc_by_section_title():
    assert classify(ch("Appendix A. Studies on intake ........ 65 Appendix B", section="Table of contents")) == "toc"
    assert classify(ch("Appendix A. Studies on intake ........ 65", section="Contents")) == "toc"


def test_front_matter():
    text = ("© European Food Safety Authority, 2015 KEY WORDS cobalamin, vitamin B12, Adequate Intake 1 On request "
            "from the European Commission, Question No EFSA-Q-2011-01227, adopted on 11 June 2015. 2 Panel members: "
            "Carlo Agostoni, Roberto Berni Canani. Correspondence: nda@efsa.europa.eu")
    assert classify(ch(text, section="Abstract")) == "front_matter"


def test_background():
    text = ("BACKGROUND AS PROVIDED BY THE EUROPEAN COMMISSION The scientific advice on nutrient intakes is "
            "important as the basis of Community action in the field of nutrition.")
    assert classify(ch(text)) == "background"
    assert classify(ch("For communication of nutrition messages to the public it is generally more appropriate "
                       "to express recommendations as foods.", section="Terms of reference as provided by the "
                       "European Commission")) == "background"


def test_numeric_table():
    text = ("Table 12: Age (years) AR PRI 1 0.90 1.14 2 0.79 0.97 3 0.73 0.90 4 0.69 0.86 5 0.69 0.85 6 0.72 0.89 "
            "7 0.74 0.91 8 0.75 0.92 9 0.75 0.92 10 0.75 0.91 11 0.75 0.91 12 0.74 0.90 13 0.73 0.90 (m), (f)")
    assert chunk_filter.digit_share(text) > chunk_filter.DIGIT_SHARE
    assert classify(ch(text, section="3.2. Dietary sources")) == "numeric_table"   # ακόμα και σε προστατευμένη


# ---------- ό,τι ΔΕΝ πρέπει να κοπεί ----------

def test_normal_text_with_few_numbers_kept():
    text = (PROSE + " The PRI is 11 mg/day for men and 16 mg/day for premenopausal women (SCF, 1993). "
            "In children aged 1 to 6 years the PRI is 7 mg/day.")
    assert chunk_filter.digit_share(text) < chunk_filter.DIGIT_SHARE
    assert classify(ch(text, section="2.2.1. Biochemical functions")) is None


def test_short_sentence_with_values_kept():
    assert classify(ch("AI 2.0 g/day for adults, 1.1 g/day for 1-3 years, 1.3 g/day for 4-6 years.")) is None


def test_summary_with_one_marker_word_kept():
    text = ("SUMMARY Following a request from the European Commission, the Panel was asked to deliver a "
            "Scientific Opinion on Dietary Reference Values, adopted on the basis of new data. " + PROSE)
    assert classify(ch(text, section="Summary")) is None


def test_abstract_with_front_matter_markers_kept():
    """Πραγματικό μοτίβο της σελ. 1: citation + © και μετά το ABSTRACT. Περιέχει τις τιμές, δεν κόβεται."""
    text = ("EFSA Journal 2015;13(10):4254 Suggested citation: EFSA NDA Panel, 2015. Scientific Opinion on Dietary "
            "Reference Values for iron. © European Food Safety Authority, 2015 ABSTRACT " + PROSE)
    assert classify(ch(text, section="Abstract")) is None


def test_mixed_abstract_end_and_keywords_kept():
    """Τέλος του Abstract (≥ MIXED_PROSE_WORDS λέξεις) και μετά KEY WORDS / Panel members: αμφιβολία -> κρατά."""
    text = (PROSE + " KEY WORDS iron, dietary reference value 1 On request from the European Commission, "
            "Question No EFSA-Q-2008-464, adopted on 24 September 2015. 2 Panel members: Carlo Agostoni.")
    assert classify(ch(text, section="Abstract")) is None


def test_mixed_summary_end_and_toc_kept():
    text = (PROSE + " TABLE OF CONTENTS Abstract ........ 1 Summary ........ 3 Background ........ 6 "
            "Terms of reference ........ 6")
    assert classify(ch(text, section="Summary")) is None


def test_introduction_under_wrong_section_label_kept():
    """Οι ετικέτες είναι ανά σελίδα: το «ASSESSMENT 1. Introduction» μπορεί να έχει ετικέτα ToR."""
    text = "ASSESSMENT 1. Introduction In 1993, the Scientific Committee for Food adopted an opinion. " + PROSE
    assert classify(ch(text, section="Terms of reference as provided by the European Commission")) is None


# ---------- ενσωμάτωση ----------

def test_filter_chunks_keeps_ids_and_reports_reasons():
    toc = "Abstract ........ 1 Summary ........ 3 Introduction ........ 7"
    chunks = [ch(PROSE, n=1), ch(toc, n=2), ch(PROSE, n=3)]
    kept, dropped = filter_chunks(chunks)
    assert [c.chunk_id for c in kept] == ["src:0001", "src:0003"]     # χωρίς επαναρίθμηση
    assert dropped == {"toc": ["src:0002"]}


def test_params_for_manifest():
    p = chunk_filter.params()
    assert p["version"] == chunk_filter.CHUNK_FILTER_VERSION and p["digit_share"] == chunk_filter.DIGIT_SHARE
