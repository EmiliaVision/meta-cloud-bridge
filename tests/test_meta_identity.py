from meta_cloud_bridge.meta.identity import (
    META_IDENTITY_CONTENT_KEY,
    build_matrix_identity_payload,
    choose_display_name,
    extract_contact_identity,
    extract_lead_identity,
    is_non_actionable_meta_attachment,
    normalize_graph_profile,
    parse_lead_fields,
)
from meta_cloud_bridge.meta.types import MetaChannel

HENRIQUE_LEAD = """Email: henriquemdaros7@gmail.com
Full name: Henrique Daros
Phone number: 27995038761
Quantos restaurantes vocês operam?: 4-10
Quem decide a contratação de novas tecnologias para os restaurantes?: Eu
Qual é o nome dos seus restaurantes?: Restaurante Perfil
"""


MAURICIO_LEAD = """Quantos restaurantes vocês operam?
1
Qual é o nome dos seus restaurantes?
Bobs
Full name
Mauricio Acordi
Email
mauricio@example.com
Phone number
+55 49 99999-9999
"""


def test_parse_lead_fields_from_colon_format():
    fields = parse_lead_fields(HENRIQUE_LEAD)

    assert fields["Email"] == "henriquemdaros7@gmail.com"
    assert fields["Full name"] == "Henrique Daros"
    assert fields["Phone number"] == "27995038761"
    assert fields["Qual é o nome dos seus restaurantes?"] == "Restaurante Perfil"

    contact = extract_contact_identity(fields)
    lead = extract_lead_identity(fields)

    assert contact == {
        "full_name": "Henrique Daros",
        "email": "henriquemdaros7@gmail.com",
        "email_source": "lead_form_message",
        "phone": "27995038761",
        "phone_source": "lead_form_message",
    }
    assert lead["restaurant_name"] == "Restaurante Perfil"
    assert lead["restaurant_count"] == "4-10"
    assert lead["decision_maker"] == "Eu"
    assert lead["raw_fields"] == fields


def test_parse_lead_fields_from_alternating_lines():
    fields = parse_lead_fields(MAURICIO_LEAD)

    assert fields["Full name"] == "Mauricio Acordi"
    assert fields["Email"] == "mauricio@example.com"
    assert fields["Phone number"] == "+55 49 99999-9999"
    assert fields["Qual é o nome dos seus restaurantes?"] == "Bobs"


def test_non_actionable_template_attachment_is_dropped():
    assert is_non_actionable_meta_attachment({"type": "template", "payload": {}})
    assert not is_non_actionable_meta_attachment(
        {"type": "template", "payload": {"url": "https://example.com/file"}}
    )
    assert not is_non_actionable_meta_attachment({"type": "image", "payload": {}})


def test_normalize_graph_profile_and_choose_display_name():
    profile = normalize_graph_profile(
        MetaChannel.INSTAGRAM_LOGIN,
        {
            "id": "1240509947924498",
            "username": "henrique_m_daros",
            "name": "Henrique Daros",
            "profile_pic": "https://example.com/pic.jpg",
            "ignored": "value",
        },
    )

    assert profile == {
        "id": "1240509947924498",
        "username": "henrique_m_daros",
        "name": "Henrique Daros",
        "profile_pic": "https://example.com/pic.jpg",
    }
    assert choose_display_name(profile, {}, "124") == "Henrique Daros"
    assert choose_display_name({}, {"full_name": "Lead Name"}, "124") == "Lead Name"


def test_build_matrix_identity_payload_uses_namespaced_contract():
    payload = build_matrix_identity_payload(
        channel=MetaChannel.INSTAGRAM_LOGIN,
        account_id="instagram-emilia",
        remote_user_id="1240509947924498",
        remote_message_id="mid.1",
        message_type="text",
        is_echo=False,
        profile={"username": "henrique_m_daros", "name": "Henrique Daros"},
        contact={"email": "henriquemdaros7@gmail.com", "email_source": "lead_form_message"},
        lead={"restaurant_name": "Restaurante Perfil"},
    )

    assert META_IDENTITY_CONTENT_KEY == "com.emiliavision.meta_cloud_bridge.identity"
    assert payload["source"] == "meta-cloud-bridge"
    assert payload["channel"] == "instagram_login"
    assert payload["account_id"] == "instagram-emilia"
    assert payload["remote_user_id"] == "1240509947924498"
    assert payload["message"] == {
        "remote_message_id": "mid.1",
        "message_type": "text",
        "is_echo": False,
    }
    assert payload["profile"]["username"] == "henrique_m_daros"
    assert payload["contact"]["email_source"] == "lead_form_message"
    assert payload["lead"]["restaurant_name"] == "Restaurante Perfil"
