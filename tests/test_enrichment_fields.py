"""New enrichment signals: social links, store platform, decision-maker contacts."""
from aol_leadfinder.enrichment.contacts import best_personal_email, extract_contacts
from aol_leadfinder.enrichment.crawler import crawl_website
from aol_leadfinder.enrichment.intelligence import detect_store_platform
from aol_leadfinder.scrapers.http import extract_social_links


def test_extract_social_links_company_pages():
    html = (
        "<a href='https://www.facebook.com/MyFactory'>fb</a>"
        "<a href='https://www.linkedin.com/company/myfactory'>li</a>"
        "<a href='https://facebook.com/sharer/sharer.php?u=x'>share</a>"
    )
    links = extract_social_links(html)
    assert links["facebook"] == "https://www.facebook.com/MyFactory"
    assert links["linkedin"] == "https://www.linkedin.com/company/myfactory"


def test_social_links_skip_widgets_and_bare():
    html = "<a href='https://facebook.com/plugins/like.php'>x</a><a href='https://facebook.com/'>bare</a>"
    assert "facebook" not in extract_social_links(html)


def test_detect_store_platform():
    assert detect_store_platform("<script src='cdn.shopify.com/x'></script>") == "Shopify"
    assert detect_store_platform("/wp-content/plugins/woocommerce/x.css") == "WooCommerce"
    assert detect_store_platform("powered by salla.sa") == "Salla"
    assert detect_store_platform("checkout via zid.store") == "Zid"
    assert detect_store_platform("plain brochure site") is None


def test_best_personal_email_skips_role_inboxes():
    assert best_personal_email(["info@x.com", "ahmed.hassan@x.com"]) == "ahmed.hassan@x.com"
    assert best_personal_email(["sales@x.com", "support@x.com"]) is None


def test_extract_contacts_role_name_email():
    text = "Ahmed Hassan - Export Manager. For logistics contact Mona Ali."
    c = extract_contacts(text, emails=["info@co.com", "ahmed@co.com"])
    assert c["role"] == "Export Manager"  # export outranks logistics
    assert c["name"] == "Ahmed Hassan"
    assert c["email"] == "ahmed@co.com"


def test_extract_contacts_arabic_role():
    c = extract_contacts("للتواصل مع مدير التصدير", emails=[])
    assert c["role"] == "Export Manager"


def test_extract_contacts_none_when_no_role():
    assert extract_contacts("just a homepage with products", emails=["info@x.com"]) == {}


def test_crawl_website_collects_facebook():
    pages = {
        "https://shop.example/": (
            "<html><body><a href='https://facebook.com/ShopCo'>fb</a>"
            "<a href='/contact'>Contact</a>"
            "<script src='https://cdn.shopify.com/s/x.js'></script>"
            "Managing Director: Sara Nabil. We export home appliances to GCC.</body></html>"
        ),
        "https://shop.example/contact": "<html><body><a href='mailto:sara@shop.example'>e</a></body></html>",
    }
    wi = crawl_website("https://shop.example/", category="Home Appliances", fetch=lambda u: pages[u], delay=0)
    assert wi.facebook == "https://facebook.com/ShopCo"
    assert wi.store_platform == "Shopify"
    assert wi.has_online_store is True
    assert wi.contact_role == "Owner / CEO"
