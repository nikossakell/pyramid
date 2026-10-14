from datetime import date, timedelta

from rule_engine.card_rules import MAX_CARDS_PER_DAY, DayActivity, card_drops

D = date(2026, 10, 13)


def act(day, meals=1, complete=False, groups=()):
    return DayActivity(day, meals, complete, frozenset(groups))


def ids(drops):
    return {c.rule_id for c in drops}


def test_no_meals_no_cards():
    assert card_drops(act(D, meals=0), []) == []


def test_logging_and_complete_day():
    assert ids(card_drops(act(D, complete=True), [])) == {"C-LOG-01", "C-DAY-01"}


def test_variety_card():
    assert "C-VAR-01" in ids(card_drops(act(D, groups=("vegetables", "fruit", "legumes")), []))


def test_non_encouraged_groups_do_not_count():
    assert "C-VAR-01" not in ids(card_drops(act(D, groups=("sweets", "salty_snacks", "fruit")), []))


def test_three_day_streak():
    hist = [act(D - timedelta(days=i)) for i in (1, 2)]
    assert "C-STR-03" in ids(card_drops(act(D), hist))


def test_streak_broken_by_gap():
    hist = [act(D - timedelta(days=1)), act(D - timedelta(days=3))]
    assert not ids(card_drops(act(D), hist)) & {"C-STR-03", "C-STR-07"}


def test_seven_day_streak_is_epic_and_cap_respected():
    hist = [act(D - timedelta(days=i)) for i in range(1, 7)]
    drops = card_drops(act(D, complete=True, groups=("vegetables", "fruit", "fish")), hist)
    assert len(drops) == MAX_CARDS_PER_DAY
    assert drops[0].rule_id == "C-STR-07" and drops[0].tier == "epic"


def test_future_history_ignored():
    assert "C-STR-03" not in ids(card_drops(act(D), [act(D + timedelta(days=1)), act(D + timedelta(days=2))]))
