from services.receive_sms_cc_catalog import parse_canada_listing_html

LISTING_SNippet = """
<a href="https://receive-sms.cc/Canada-Phone-Number/12368791988">Canada Phone Number +1 2368791988 41 6 hours ago</a>
<a href="https://receive-sms.cc/Canada-Phone-Number/12368791977">Canada Phone Number +1 2368791977 14 6 hours ago</a>
"""


def test_parse_canada_listing() -> None:
    entries = parse_canada_listing_html(LISTING_SNippet)
    assert len(entries) == 2
    assert entries[0].phone_e164 == "+12368791988"
    assert entries[0].message_count == 41
    assert entries[1].message_count == 14
