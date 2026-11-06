"""
ai_pipeline/presentation/prompts.py — τα prompts του Krikri για τη φιλική διατύπωση (Βήμα 4.1).

ΑΠΟΚΛΙΣΗ ΑΠΟ ΤΟ final_plan (τεκμηριωμένη):
Το PROMPT_TEMPLATE του πλάνου περνά στο LLM «Current intake», «Target», «Status» και ζητά να μην αλλάξει
τους αριθμούς. Εδώ το Krikri ΔΕΝ βλέπει κανέναν αριθμό: παίρνει το ΕΓΚΕΚΡΙΜΕΝΟ σταθερό κείμενο (templates.py)
και το ξαναγράπει πιο φιλικά. Λόγοι:
- αριθμοί δεν φτάνουν στο παιδί (απόφαση Φάσης 2, EFSA: «DRVs are not nutrient goals for individuals»)·
  ό,τι δεν μπαίνει στο prompt δεν μπορεί να διαρρεύσει στην απάντηση·
- το LLM αλλάζει μόνο τη διατύπωση ενός κειμένου που έχει ήδη εγκρίνει διαιτολόγος, όχι το περιεχόμενο·
- τα ρητά όρια (ποιο θρεπτικό, ποιες τροφές, ποια κατεύθυνση) είναι ακριβώς αυτά που ελέγχει ο validator (4.2).

Η ηλικία περνά ως εύρος (10-12 / 13-16), όχι ως ακριβής τιμή: αρκεί για το ύφος (ελαχιστοποίηση δεδομένων).
Κάθε αλλαγή κειμένου εδώ = νέο PROMPT_VERSION (μπαίνει στο audit).
"""
import hashlib
import json
from typing import Optional

from rule_engine.models import IntakeStatus, RuleDecision

from .lexicon import Lexicon
from .templates import MAX_FOOD_GROUPS_IN_MESSAGE

PROMPT_VERSION = "0.1"

SYSTEM_PROMPT = (
    "Είσαι βοηθός διατύπωσης σε μια εκπαιδευτική εφαρμογή για παιδιά και εφήβους. "
    "Παίρνεις ένα μήνυμα που έχει εγκρίνει διαιτολόγος και το ξαναγράφεις πιο φιλικά, με απλά ελληνικά, "
    "σε δεύτερο ενικό. Δεν αλλάζεις το νόημά του.\n"
    "ΑΥΣΤΗΡΟΙ ΚΑΝΟΝΕΣ:\n"
    "1. Μόνο ελληνικά. Μία ή δύο σύντομες προτάσεις, έως 250 χαρακτήρες.\n"
    "2. Κανένας αριθμός, ούτε με ψηφία ούτε ολογράφως (π.χ. «δύο», «μισό»). Καμία μονάδα μέτρησης.\n"
    "3. Μην αναφέρεις θερμίδες, βάρος, κιλά, δίαιτα, σώμα ή εμφάνιση.\n"
    "4. Μην χαρακτηρίζεις φαγητά «καλά», «κακά» ή «ανθυγιεινά». Μη γράφεις «μην φας» ή «κόψε».\n"
    "5. Καμία διάγνωση, ιατρική συμβουλή ή αναφορά σε συμπληρώματα, φάρμακα ή ασθένειες.\n"
    "6. Ανάφερε ΜΟΝΟ το θρεπτικό συστατικό και ΜΟΝΟ τις τροφές που σου δίνονται. Καμία άλλη τροφή, "
    "κανένα άλλο θρεπτικό συστατικό, καμία νέα συμβουλή.\n"
    "7. Γράψε μόνο το νέο μήνυμα: χωρίς εισαγωγή, χωρίς εισαγωγικά, χωρίς emoji."
)

_DIRECTION = {
    IntakeStatus.LIKELY_INADEQUATE: "Το μήνυμα προτείνει να τρώει ΠΙΟ ΣΥΧΝΑ αυτές τις τροφές. Μη γράψεις «λιγότερο».",
    IntakeStatus.UNCERTAIN: "Το μήνυμα προτείνει ήπια να τρώει λίγο πιο συχνά αυτές τις τροφές. Μη γράψεις «λιγότερο».",
    IntakeStatus.NO_CONCLUSION: "Το μήνυμα απλώς δίνει μια ιδέα για τροφές. Μη ζητήσεις ούτε περισσότερο ούτε λιγότερο.",
    IntakeStatus.ABOVE_REFERENCE: "Το μήνυμα προτείνει να τρώει ΠΙΟ ΣΠΑΝΙΑ αυτές τις τροφές. Μη γράψεις «περισσότερο».",
    IntakeStatus.LIKELY_ADEQUATE: "Το μήνυμα είναι επιβράβευση. Μη ζητήσεις ούτε περισσότερο ούτε λιγότερο.",
}


def age_band(age_years: Optional[int]) -> str:
    if age_years is None:
        return "10-16"
    return "10-12" if age_years <= 12 else "13-16"


def build_messages(decision: RuleDecision, template_text: str, lexicon: Lexicon,
                   age_years: Optional[int] = None) -> list[dict]:
    if decision.status not in _DIRECTION:
        raise ValueError(f"status '{decision.status.value}' is not presented to the child")
    nutrient = lexicon.nutrients[decision.nutrient_id].name_el
    groups = decision.food_group_hint[:MAX_FOOD_GROUPS_IN_MESSAGE]
    foods = ", ".join(lexicon.food_groups[g].name_el for g in groups) if groups else "καμία (μην αναφέρεις τρόφιμα)"
    user = (
        f"Ηλικία αναγνώστη: {age_band(age_years)} ετών.\n"
        f"Θρεπτικό συστατικό: {nutrient}\n"
        f"Επιτρεπόμενες τροφές: {foods}\n"
        f"Κατεύθυνση: {_DIRECTION[decision.status]}\n"
        f"Εγκεκριμένο μήνυμα: {template_text}\n"
        "Νέα διατύπωση:"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def prompt_hash(messages: list[dict], params: dict) -> str:
    """sha256 του ακριβούς αιτήματος (μηνύματα + παράμετροι), για το audit (Κανόνας 5)."""
    blob = json.dumps({"messages": messages, "params": params}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
