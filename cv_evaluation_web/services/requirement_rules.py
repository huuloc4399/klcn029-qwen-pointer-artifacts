"""JD requirement rules: one source for the rater guide, the model prompts and the code checks.

The rater guide (downstream/data/package_rater.py) prints RULES as bullets; rubric_scoring.REQUIREMENT_GUIDE
puts the same bullets in every model prompt (M1–M4 and P); evaluator.py builds its implication and synonym
tables from SKILL_IMPLIES, SOFT_SKILLS and CONCEPTS, which P and K use to check quotes. Changing a rule here
changes all three, so raters and models cannot drift apart. Bump VERSION with every change.
"""

from __future__ import annotations

VERSION = "2026-10-17"

# Direct implication: using the key technology means using the required one (target ← sources).
SKILL_IMPLIES: dict[str, tuple[str, ...]] = {
    "Java": ("Spring Boot",),
    "PHP": ("Laravel",),
    "Python": ("Django", "FastAPI", "Flask"),
    "Node.js": ("Express", "NestJS"),
    "JavaScript": ("React", "Vue.js", "Angular"),
    "C#": ("ASP.NET MVC",),
    "REST API": ("FastAPI", "Express", "Spring Boot", "Django"),
}

# Soft skills count only under their own name or its translation (Vietnamese, English).
SOFT_SKILLS: tuple[tuple[str, str], ...] = (
    ("làm việc nhóm", "teamwork"),
    ("giải quyết vấn đề", "problem-solving"),
    ("tư duy logic", "logical thinking"),
    ("tư duy phân tích", "analytical thinking"),
    ("giao tiếp", "communication"),
)

# Requirements that are concepts, not tools: how a JD names them, what in a CV counts as the concept itself,
# and base technologies that alone are only a loose association (unclear).
CONCEPTS: tuple[dict[str, tuple[str, ...] | str], ...] = (
    {"name": "Responsive web design", "jd": ("responsive",),
     "cv": ("responsive", "media query", "mobile-first", "mobile-friendly", "giao diện tương thích di động"),
     "base": ("CSS", "Bootstrap")},
    {"name": "OOP", "jd": ("oop", "hướng đối tượng", "object-oriented"),
     "cv": ("OOP", "hướng đối tượng", "object-oriented", "class", "kế thừa", "inheritance", "design pattern"),
     "base": ("Java", "C#")},
    {"name": "Thiết kế CSDL", "jd": ("database design", "thiết kế csdl", "thiết kế cơ sở dữ liệu"),
     "cv": ("thiết kế CSDL", "thiết kế cơ sở dữ liệu", "database design", "ERD", "schema", "chuẩn hóa"),
     "base": ("MySQL", "SQL Server")},
    {"name": "Linux", "jd": ("linux",), "cv": ("Linux", "Ubuntu", "CentOS"), "base": ("Docker",)},
    {"name": "Tiếng Anh", "jd": ("english", "tiếng anh"), "cv": ("English", "tiếng Anh", "IELTS", "TOEIC", "TOEFL"),
     "base": ()},
)

# Loose associations between tools in the skill dictionary (usually together, never required) → unclear.
LOOSE: tuple[tuple[str, str], ...] = (("Git", "CI/CD"), ("React", "TypeScript"))


def _implies_text() -> str:
    parts = [f"{', '.join(sources)} → {target}" for target, sources in SKILL_IMPLIES.items() if target != "REST API"]
    return "; ".join(parts) + f"; dựng backend/API bằng {', '.join(SKILL_IMPLIES['REST API'])} → REST API"


def _concepts_text() -> str:
    parts = []
    for c in CONCEPTS:
        if not c["base"]:
            continue
        parts.append(f"{c['name']}: tính khi CV nêu {', '.join(c['cv'])}; chỉ có {', '.join(c['base'])} → unclear")
    return ". ".join(parts)


RULES: tuple[str, ...] = (
    "Chọn trạng thái theo thứ tự. (1) CV nêu chính yêu cầu (đúng tên, tên viết tắt, cách gọi khác, công nghệ bao hàm "
    "trực tiếp, hoặc kỹ thuật cụ thể thuộc khái niệm): có trong dự án, kinh nghiệm, chứng chỉ hoặc hoạt động → met; "
    "chỉ ở mục kỹ năng, mục tiêu hoặc giới thiệu → mentioned_only. (2) CV chỉ có dấu hiệu có thể là yêu cầu nhưng chưa "
    "đủ để khẳng định (công nghệ nền, liên quan lỏng, câu chung chung, tính năng tương tự ở lĩnh vực khác) → unclear, "
    "ghi CV có gì. (3) Không có gì, hoặc CV có thứ khác thay cho yêu cầu (công cụ khác cùng loại, khả năng khác) → missing.",
    "unclear không tính vào tỉ lệ C8. Chỉ chọn unclear khi thật sự thiếu căn cứ; CV đã nêu rõ thì chọn met hoặc "
    "mentioned_only, CV không có gì thì chọn missing.",
    "Bỏ qua mức độ: JD ghi 'thành thạo Java', CV chỉ liệt kê Java ở mục kỹ năng → mentioned_only; mức độ phản ánh ở C3.",
    "Yêu cầu có lựa chọn thay thế ('React hoặc Vue') → CV có một trong các lựa chọn là đủ.",
    f"Bao hàm trực tiếp, tính như CV có kỹ năng được yêu cầu: {_implies_text()}.",
    "Yêu cầu là khái niệm hoặc kỹ thuật (không phải tên công cụ) → cần CV nêu chính khái niệm đó hoặc một kỹ thuật cụ "
    f"thể thuộc nó; chỉ có công nghệ nền → unclear. {_concepts_text()}.",
    "Liên quan lỏng khác (thường đi cùng nhưng không bắt buộc) → unclear: "
    + "; ".join(f"{a} → {b}" for a, b in LOOSE) + ".",
    "Câu tự nhận kinh nghiệm ('Experienced in X', 'Có kinh nghiệm với X') ở mục kỹ năng hoặc giới thiệu, không gắn dự "
    "án → mentioned_only; X xuất hiện trong một dự án → met.",
    "Ngoại ngữ, kỹ năng mềm: có chứng chỉ (TOEIC, IELTS) hoặc việc làm cụ thể (thuyết trình bằng tiếng Anh, trưởng "
    "nhóm) → met; chỉ tự ghi → mentioned_only. CV viết bằng tiếng Anh không phải bằng chứng về tiếng Anh → unclear.",
    "Kỹ năng mềm chỉ tính khi đúng tên hoặc đồng nghĩa ("
    + "; ".join(f"{vi} = {en}" for vi, en in SOFT_SKILLS)
    + "). Kỹ năng khác không thay thế nhau (problem-solving không tính cho tư duy logic) → missing.",
    "Công cụ khác cùng loại (MySQL thay PostgreSQL, GitHub thay GitLab, Trello thay Jira) → missing, trừ khi JD ghi "
    "'hoặc', 'or similar', 'tương đương'. Khả năng khác cùng lĩnh vực (JD cần giao tiếp tiếng Anh, CV chỉ ghi đọc tài "
    "liệu kỹ thuật) → missing.",
    "Yêu cầu là loại công cụ kèm ví dụ ('E-commerce platforms: Shopify, WordPress or other') → chỉ tính công cụ cùng "
    "loại (WooCommerce, Magento); tự xây một website bán hàng → missing.",
    "Yêu cầu về lĩnh vực (fintech, tài chính – ngân hàng) → dự án phải thuộc lĩnh vực đó; chỉ có một tính năng liên quan "
    "trong dự án khác lĩnh vực (cổng thanh toán trong web bán hàng) → unclear.",
    "Nhóm kỹ thuật kèm ví dụ trong ngoặc ('Hiệu năng web (code splitting, lazy loading)') → met khi dự án hoặc kinh "
    "nghiệm nêu ít nhất một kỹ thuật cụ thể trong ngoặc hoặc cùng loại; chỉ ghi chung 'tối ưu hiệu năng' → unclear.",
)


def prompt_text() -> str:
    """The rules as they go into a model prompt."""
    return (f"Quy tắc xét từng yêu cầu của JD (bản {VERSION}, cùng danh sách với hướng dẫn người chấm):\n"
            + "\n".join(f"- {rule}" for rule in RULES))
