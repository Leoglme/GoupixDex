"""
eBay condition descriptor IDs for graded trading cards (categories 183050, 183454, 261328).

Source: https://developer.ebay.com/api-docs/user-guides/static/mip-user-guide/mip-enum-condition-descriptor-ids-for-trading-cards.html
"""

from __future__ import annotations

# Inventory API: conditionDescriptors[].name
EBAY_DESCRIPTOR_PROFESSIONAL_GRADER = "27501"
EBAY_DESCRIPTOR_GRADE = "27502"
EBAY_DESCRIPTOR_CERTIFICATION = "27503"
# Ungraded card surface condition
EBAY_DESCRIPTOR_CARD_CONDITION = "40001"

# Item condition enum for graded slabs
EBAY_CONDITION_GRADED = "LIKE_NEW"

# (French UI label, value id) — aligné sur l’éditeur eBay.fr
EBAY_PROFESSIONAL_GRADER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Professional Sports Authenticator (PSA)", "275010"),
    ("Beckett Collectors Club Grading (BCCG)", "275011"),
    ("Beckett Vintage Grading (BVG)", "275012"),
    ("Beckett Grading Services (BGS)", "275013"),
    ("Certified Sports Guaranty (CSG)", "275014"),
    ("Certified Guaranty Company (CGC)", "275015"),
    ("Sportscard Guaranty Corporation (SGC)", "275016"),
    ("K Sportscard Authentication (KSA)", "275017"),
    ("Gem Mint Authentication (GMA)", "275018"),
    ("Hybrid Grading Approach (HGA)", "275019"),
    ("International Sports Authentication (ISA)", "2750110"),
    ("Professional Card Authenticator (PCA)", "2750111"),
    ("Gold Standard Grading (GSG)", "2750112"),
    ("Platin Grading Service (PGS)", "2750113"),
    ("MNT Grading (MNT)", "2750114"),
    ("Technical Authentication & Grading (TAG)", "2750115"),
    ("Rare Edition (Rare)", "2750116"),
    ("Revolution Card Grading (RCG)", "2750117"),
    ("Premier Card Grading (PCG)", "2750118"),
    ("Ace Grading (Ace)", "2750119"),
    ("Card Grading Australia (CGA)", "2750120"),
    ("Trading Card Grading (TCG)", "2750121"),
    ("ARK Grading (ARK)", "2750122"),
    ("Autre", "2750123"),
)

# (label, value id) — suite numérique officielle eBay
EBAY_GRADE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("10", "275020"),
    ("9.5", "275021"),
    ("9", "275022"),
    ("8.5", "275023"),
    ("8", "275024"),
    ("7.5", "275025"),
    ("7", "275026"),
    ("6.5", "275027"),
    ("6", "275028"),
    ("5.5", "275029"),
    ("5", "2750210"),
    ("4.5", "2750211"),
    ("4", "2750212"),
    ("3.5", "2750213"),
    ("3", "2750214"),
    ("2.5", "2750215"),
    ("2", "2750216"),
    ("1.5", "2750217"),
    ("1", "2750218"),
    ("Authentic", "2750219"),
    ("Authentic Altered", "2750220"),
    ("Authentic - Trimmed", "2750221"),
    ("Authentic - Coloured", "2750222"),
)

_VALID_GRADER_IDS = frozenset(v for _, v in EBAY_PROFESSIONAL_GRADER_OPTIONS)
_VALID_GRADE_IDS = frozenset(v for _, v in EBAY_GRADE_OPTIONS)


def is_valid_grader_value_id(value_id: str | None) -> bool:
    return bool(value_id) and value_id in _VALID_GRADER_IDS


def is_valid_grade_value_id(value_id: str | None) -> bool:
    return bool(value_id) and value_id in _VALID_GRADE_IDS


def graded_condition_descriptor_payloads(
    *,
    grader_value_id: str,
    grade_value_id: str,
    certification_text: str | None,
) -> list[dict[str, object]]:
    """JSON fragments for ``inventory_item.conditionDescriptors`` (graded TCG)."""
    out: list[dict[str, object]] = [
        {"name": EBAY_DESCRIPTOR_PROFESSIONAL_GRADER, "values": [grader_value_id]},
        {"name": EBAY_DESCRIPTOR_GRADE, "values": [grade_value_id]},
    ]
    cert = (certification_text or "").strip()[:30]
    if cert:
        # Certificat : texte libre dans ``additionalInfo`` (max 30 car.) — pas de ``values``.
        out.append({"name": EBAY_DESCRIPTOR_CERTIFICATION, "additionalInfo": cert})
    return out
