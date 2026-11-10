"""Κλειδιά πρόσβασης: μορφή, εντροπία, κανονικοποίηση (Crockford), HMAC με pepper."""
import re

from app.core.security import (CROCKFORD, KEY_BITS, generate_access_key, key_hmac, normalize_access_key)

FORMAT = re.compile(r"^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$")


def test_format_and_entropy():
    keys = {generate_access_key() for _ in range(2000)}
    assert len(keys) == 2000 and all(FORMAT.match(k) for k in keys)
    assert KEY_BITS >= 60 and len(CROCKFORD) == 32 and not set("ILOU") & set(CROCKFORD)


def test_normalisation():
    assert normalize_access_key("abcd-efgh-jkmn") == "ABCDEFGHJKMN"
    assert normalize_access_key(" ab cd-ef gh-jk mn ") == "ABCDEFGHJKMN"
    assert normalize_access_key("IOLO-0000-1111") == "1010" + "00001111"    # I/L -> 1, O -> 0
    for bad in ("", "ABCD-EFGH-JKM", "ABCD-EFGH-JKMNP", "ABCD-EFGH-JKMU", "ΑΒΓΔ-EFGH-JKMN", "x" * 65, None, 123):
        assert normalize_access_key(bad) is None


def test_hmac_depends_on_pepper_and_is_stable():
    k = normalize_access_key(generate_access_key())
    assert key_hmac(k, "pepper-1") == key_hmac(k, "pepper-1")
    assert key_hmac(k, "pepper-1") != key_hmac(k, "pepper-2")
    assert len(key_hmac(k, "p")) == 64 and k not in key_hmac(k, "p")
