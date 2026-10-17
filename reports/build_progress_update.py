"""Build the concise advisor progress update (Markdown + Word) from measured artifacts.

Word layout follows the faculty sample report (Example_PhatHienTinGiaTiengVietNNTN_0206.pdf):
A4, Times New Roman 13, justified, line spacing 1.3, margins 2.5/2.5/3.5/2.5 cm,
bordered cover page with the school logo, italic table captions above tables.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
STEM = 'BAO_CAO_TIEN_DO_GVHD_2026-10-11'
SHIFT = ROOT / 'training/audits/gold40_input_shift_2026-10-11_v1/input_shift.json'
DIAG = ROOT / 'training/audits/gold40_generalization_2026-10-11_v2/diagnostics.json'
LOGO = OUT / 'assets/huit_logo.png'
FONT = 'Times New Roman'
TOPIC_LINES = ['NGHIÊN CỨU HỆ THỐNG HỖ TRỢ', 'ĐÁNH GIÁ VÀ CẢI THIỆN CV', 'SỬ DỤNG MÔ HÌNH NGÔN NGỮ LỚN']
ADVISOR = 'ThS. Huỳnh Thị Cẩm Dung'
STUDENTS = ['2001230468-Nguyễn Hữu Lộc-14DHTH01', '2001230364-Dương Chí Khải-14DHTH01', '2001230169-Lê Tâm Đắc-14DHTH03']
DATE_LINE = 'TP. HỒ CHÍ MINH, tháng 10 năm 2026'


def p(value: float) -> str:
    return f'{value * 100:.2f}%'.replace('.', ',')


def blocks() -> list[tuple]:
    shift = json.loads(SHIFT.read_text(encoding='utf-8'))
    diag = json.loads(DIAG.read_text(encoding='utf-8'))
    syn, real = shift['input_profile']['synthetic_train'], shift['input_profile']['gold40_real']
    out = shift['output_profile_gold40']
    f1 = {m: diag['real_micro_f1'][m]['f1'] for m in ('B0', 'B1', 'P0', 'P1')}
    test = diag['synthetic']['test']
    p0 = out['P0']['long_text_buckets']
    b = []
    tables = 0
    H = lambda level, text: b.append(('heading', level, text))
    P = lambda text: b.append(('paragraph', text))
    L = lambda text, path=None: b.append(('bullet', text, path))

    def T(caption, headers, rows, widths, align):
        nonlocal tables
        tables += 1
        b.append(('caption', f'Bảng {tables}: {caption}'))
        b.append(('table', headers, rows, widths, align))

    H(1, '1. Tóm tắt')
    P('Nhóm đã hoàn thành pipeline trích xuất CV sang CVSchema 2.0, hai giai đoạn huấn luyện QLoRA trên Qwen3-4B, '
      'bộ đánh giá có truy vết, bộ nhãn chuẩn GOLD40 (20 CV tiếng Anh, 20 CV tiếng Việt) và demo đánh giá CV theo JD trên Colab.')
    P(f'Kết quả chính: mô hình fine-tune đạt Field Micro F1 {p(test["adapter"]["f1"])} trên test tổng hợp, '
      f'nhưng trên CV thật GOLD40 chỉ đạt {p(f1["B1"])}, thấp hơn Qwen gốc ({p(f1["B0"])}). '
      'Nhóm đã phân tích và xác định nguyên nhân chính: dữ liệu train tổng hợp khác CV thật cả về hình thức văn bản, '
      'quy tắc gán nhãn lẫn độ phủ, nên mô hình học thuộc quy ước của bộ tổng hợp thay vì học cách đọc CV. '
      'Báo cáo này trình bày bằng chứng và kế hoạch khắc phục.')

    H(1, '2. Công việc đã hoàn thành')
    P('Các hạng mục đã hoàn thành đến ngày 11/10/2026 được tổng hợp trong Bảng 1.')
    T('Các hạng mục đã hoàn thành', ['Hạng mục', 'Kết quả'], [
        ['Dữ liệu', '80 CV thật (60 EN, 20 VI); 1.000 CV tổng hợp chia 850/75/75; schema CV/JD'],
        ['Nhãn chuẩn', 'GOLD40 chốt ngày 10/10 (40/40 hợp lệ schema); web app gán nhãn và web app rà nhãn độc lập'],
        ['OCR', 'Pilot trên 5 trang tiếng Việt: VietOCR đạt Token F1 94–97%, PaddleOCR Latin 55,81%; đã chọn phương án lai cho tiếng Việt'],
        ['Huấn luyện', 'Stage 1 Full JSON và stage 2 Hybrid Pointer (QLoRA, 1 epoch, Colab T4); đủ adapter, log, audit'],
        ['Đánh giá', 'Parser và metric khóa trước test; đã đo trên validation/test tổng hợp, 80 CV thật và GOLD40'],
        ['Kiểm chứng/retry', 'P1 nâng tỷ lệ CV hợp lệ schema trên 80 CV thật từ 71/80 lên 78/80'],
        ['Hạ nguồn', 'Matching M1/M2/M3, chấm điểm và gợi ý có mã và demo; chưa có benchmark có nhãn'],
        ['Demo', 'Web Flask chạy local; Colab chạy đầu cuối CV–JD; cloud tạm dừng do ngân sách'],
    ], [3.5, 11.5], 'LL')

    H(1, '3. Kết quả trích xuất')
    P('B0 là Qwen gốc; B1 là adapter stage 1 (Full JSON); P0 là adapter stage 2 (Pointer); P1 là P0 cộng kiểm chứng và retry. '
      'Bảng 2 so sánh Field Micro F1 của bốn cấu hình trên test tổng hợp và trên GOLD40.')
    synthetic_test = {'B0': p(test['base']['f1']), 'B1': p(test['adapter']['f1']),
                      'P0': p(diag['pointer_synthetic']['test']['micro']['f1']), 'P1': 'Chưa đo'}
    T('Field Micro F1 trên test tổng hợp và GOLD40', ['Cấu hình', 'Test tổng hợp', 'GOLD40 thật'],
      [[m, synthetic_test[m], p(f1[m])] for m in ('B0', 'B1', 'P0', 'P1')], [4.0, 5.5, 5.5], 'CCC')
    P('Trên GOLD40, khoảng tin cậy 95% (bootstrap ghép cặp theo CV) của chênh lệch B1 so với B0 là −22,58 đến −11,75 điểm phần trăm; '
      'khoảng không chứa 0 nên mức giảm không phải dao động ngẫu nhiên giữa các CV trong nhóm này. P1 tốt hơn P0 (+3,14 điểm) '
      'nhưng vẫn thấp hơn B0. Tiếng Việt kém hơn tiếng Anh ở mọi cấu hình (B0: 72,23% EN, 58,52% VI). '
      'GOLD40 được dùng để phân tích lỗi nên từ nay không còn là tập test độc lập.')

    H(1, '4. Nguyên nhân mô hình tốt trên dữ liệu tổng hợp nhưng kém trên CV thật')
    P('Eval loss giảm đều đến cuối cả hai run (stage 1: 0,0154 → 0,0112 → 0,0109), nên chưa thấy dấu hiệu train quá lâu. '
      'Nguyên nhân là test tổng hợp cùng nguồn sinh, cùng 3 template và cùng quy tắc nhãn với train: F1 99% đo mức tuân theo quy ước '
      f'của bộ tổng hợp. Dấu hiệu: tỷ lệ CV đúng toàn bộ trên test tổng hợp tăng từ {test["base"]["document_exact_rate"]*75:.0f}/75 (Qwen gốc) '
      f'lên {test["adapter"]["document_exact_rate"]*75:.0f}/75 sau fine-tune. Có ba nhóm lệch, đều có số đo.')

    H(2, '4.1. Lệch hình thức văn bản đầu vào')
    P('Bảng 3 so sánh hình thức văn bản nguồn đưa vào mô hình giữa dữ liệu train tổng hợp và CV thật.')
    T('Hình thức văn bản nguồn của train tổng hợp và GOLD40', ['Đặc điểm văn bản nguồn', 'Train tổng hợp', 'GOLD40 thật'], [
        ['Summary nằm trọn trên một dòng', f'{syn["summary_equal_to_one_source_line"][0]}/{syn["summary_equal_to_one_source_line"][1]}',
         f'{real["summary_equal_to_one_source_line"][0]}/{real["summary_equal_to_one_source_line"][1]}'],
        ['CV có dòng gạch đầu dòng (•, -)', f'{syn["cvs_with_list_marker_lines"]}/{syn["cv_count"]}', f'{real["cvs_with_list_marker_lines"]}/{real["cv_count"]}'],
        ['CV có một dòng chứa từ 3 kỹ năng trở lên', f'{syn["cvs_with_a_line_holding_3plus_labeled_hard_skills"]}/{syn["cv_count"]}',
         f'{real["cvs_with_a_line_holding_3plus_labeled_hard_skills"]}/{real["cv_count"]}'],
        ['CV tiếng Việt', '0/850', '20/40'],
    ], [8.0, 3.5, 3.5], 'LCC')
    P('Mô hình học các quy tắc tắt: mỗi dòng trong mục Skills là một kỹ năng, mỗi đoạn văn là một dòng. Khi gặp CV thật, các quy tắc này gây lỗi:')
    L(f'B1 chép nguyên dòng "Programming: C#, JavaScript, Python" thành một kỹ năng; {out["B1"]["hard_skill_items_with_colon"]}/{out["B1"]["hard_skill_items"]} '
      f'mục kỹ năng của B1 chứa dấu ":" (B0: {out["B0"]["hard_skill_items_with_colon"]}/{out["B0"]["hard_skill_items"]}). '
      'F1 kỹ năng cứng của B1 chỉ 13,69%, của B0 là 58,33%.')
    L(f'P0 trỏ khoảng dòng quá ngắn cho văn bản dài bị ngắt nhiều dòng, nên summary bị cắt giữa câu. '
      f'Trong {out["P0"]["predicted_long_text_items"]} văn bản dài P0 sinh ra (gold có {out["gold_long_text_items"]}): {p0["exact"]} khớp, '
      f'{p0["differs_only_by_list_markers"]} chỉ sai vì giữ ký hiệu gạch đầu dòng, {p0["truncated_prefix_of_gold"]} bị cắt cụt, '
      f'{p0["contains_gold_plus_extra_text"]} lấy lố sang phần khác, {p0["fragment_inside_gold"]} chỉ là một đoạn nhỏ. '
      'Vì vậy Long Text F1 của P0 chỉ 17,39%.')
    L('B1 chèn dòng chức danh vào đầu summary và bỏ sót cụm từ ở đoạn bị ngắt từng từ một dòng.')

    H(2, '4.2. Lệch quy tắc gán nhãn')
    L('Converter dữ liệu tổng hợp không đưa công nghệ của dự án vào hard skills (543/544 CV train có công nghệ dự án bị thiếu), '
      'trong khi hướng dẫn gán nhãn gold có đưa vào. Ngoại ngữ cũng không được đưa vào nhãn kỹ năng.')
    L('Soft skills trong train chỉ có một giá trị duy nhất là "Communication".')

    H(2, '4.3. Thiếu độ phủ dữ liệu train')
    L('Không có CV tiếng Việt; không có ví dụ có giá trị cho GitHub (gold có 30), GPA (28), activities (6), awards (2).')
    L('Chỉ 3 template; 1 epoch trên dữ liệu đồng nhất như vậy đủ để thói quen tổng hợp lấn át năng lực đọc CV sẵn có của Qwen gốc. '
      'B1 còn sinh activities dạng object ở 3 CV tiếng Việt, làm hỏng schema.')
    P('Giới hạn: phân tích này thực hiện hậu kiểm trên GOLD40; nhãn gold đang được rà lại. Các cải tiến dưới đây phải được xác nhận trên dữ liệu mới.')

    H(1, '5. Kế hoạch khắc phục')
    P('Kế hoạch gồm tám bước, đi từ các thay đổi không cần GPU đến huấn luyện lại và xác nhận trên dữ liệu mới (Bảng 4).')
    T('Kế hoạch khắc phục', ['Bước', 'Nội dung', 'Cần GPU', 'Kiểm chứng'], [
        ['1', 'Hậu xử lý Pointer: bỏ ký hiệu gạch đầu dòng, nối dòng bị ngắt, dừng khoảng dòng tại tiêu đề mục', 'Không', 'Unit test, dev thật'],
        ['2', 'Tách kỹ năng dạng "Nhóm: a, b, c"; hợp công nghệ dự án và ngoại ngữ vào hard skills theo quy tắc gold', 'Không', 'Unit test, dev thật'],
        ['3', 'Chốt quy tắc nhãn chung cho train, gold và prompt; hoàn tất rà GOLD40 bằng PDF', 'Không', 'Biên bản phân xử, gold v2'],
        ['4', 'Lập tập dev thật: 37 CV tiếng Anh còn lại của Real80 (bỏ EN043 trùng EN024 trong GOLD40) cộng CV tiếng Việt mới thu thập, vì cả 20 CV tiếng Việt đã nằm trong GOLD40', 'Không', 'Hai người gán, đo đồng thuận'],
        ['5', 'So sánh B0 + hậu xử lý, B0 few-shot với CV thật, P1 + hậu xử lý trên tập dev', 'Chỉ suy luận', 'F1 dev thật, EN/VI'],
        ['6', 'Dataset v2: render CV tổng hợp ra PDF nhiều bố cục rồi trích text như pipeline thật; thêm tiếng Việt, các trường còn thiếu và CV thật', 'Không', 'Thống kê như Bảng 3'],
        ['7', 'Huấn luyện lại; chọn checkpoint theo F1 trên dev thật, không theo loss tổng hợp', 'Có', 'So với baseline tốt nhất ở bước 5'],
        ['8', 'Xác nhận cấu hình cuối trên nhóm CV mới, khóa trước khi chạy', 'Có', 'Báo kết quả một lần'],
    ], [1.7, 7.3, 2.3, 3.7], 'CLCL')
    P('Nguyên tắc: giữ nguyên metric v1 và kết quả đã đo; không sửa gold theo output mô hình; không đưa GOLD40 vào train. '
      'Nếu sau bước 7 fine-tune vẫn không vượt Qwen gốc, nhóm sẽ dùng Qwen gốc kèm hậu xử lý và kiểm chứng cho hệ thống, '
      'và trình bày phân tích dịch chuyển miền như một kết quả nghiên cứu.')

    H(1, '6. Đề nghị ý kiến giảng viên')
    L('Nhóm đề xuất dùng 37 CV tiếng Anh còn lại của Real80 làm tập phát triển, thu thập thêm CV tiếng Việt cho tập phát triển, '
      'và một nhóm CV mới làm tập kiểm tra cuối. Giảng viên có đồng ý và có gợi ý nguồn thu thập CV không?')
    L('Nếu fine-tune không vượt Qwen gốc, kết luận "Qwen gốc + hậu xử lý + kiểm chứng" kèm phân tích nguyên nhân có đáp ứng yêu cầu của đề tài không?')
    L('Phạm vi hard skills có nên gồm công nghệ dự án và ngoại ngữ như hướng dẫn gold hiện tại không?')

    H(1, '7. Tài liệu kèm theo')
    for text, path in [('Báo cáo chi tiết cấu hình huấn luyện, số liệu và phụ lục từng trường:',
                        'reports/BAO_CAO_TONG_HOP_DU_LIEU_HUAN_LUYEN_VA_DANH_GIA_2026-10-11.docx'),
                       ('Chẩn đoán lệch nhãn và độ phủ dữ liệu:', 'reports/GOLD40_CHAN_DOAN_TONG_QUAT_HOA_VA_RASOAT_2026-10-11.md'),
                       ('Script và số đo lệch hình thức đầu vào ở mục 4.1:', 'training/audits/gold40_input_shift_2026-10-11_v1/'),
                       ('Kết quả GOLD40 đã khóa:', 'training/evaluation/results/gold40_b0_b1_p0_p1_v1/')]:
        L(text, path)
    return b


def markdown(content: list[tuple]) -> str:
    lines = ['# Báo cáo tiến độ thực hiện khóa luận', '',
             f'Đề tài: {" ".join(TOPIC_LINES).capitalize()}  ',
             f'Giảng viên hướng dẫn: {ADVISOR}  ',
             'Sinh viên thực hiện: ' + '; '.join(STUDENTS) + '  ', DATE_LINE.capitalize(), '']
    for block in content:
        kind = block[0]
        if kind == 'heading':
            lines += ['#' * (block[1] + 1) + ' ' + block[2], '']
        elif kind == 'paragraph':
            lines += [block[1], '']
        elif kind == 'bullet':
            lines += ['- ' + block[1] + (f' `{block[2]}`' if block[2] else ''), '']
        elif kind == 'caption':
            lines += [f'*{block[1]}*', '']
        else:
            headers, rows = block[1], block[2]
            lines.append('| ' + ' | '.join(headers) + ' |')
            lines.append('| ' + ' | '.join('---' for _ in headers) + ' |')
            lines += ['| ' + ' | '.join(str(c).replace('|', '/') for c in row) + ' |' for row in rows]
            lines.append('')
    return '\n'.join(lines)


# ---------- Word ----------

def set_font(run, size=13, bold=False, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)
    fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    for attr in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
        fonts.set(qn(attr), FONT)


def style_fonts(style, size, bold=False, italic=False):
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    style.font.color.rgb = RGBColor(0, 0, 0)
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    for attr in ('w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme'):
        fonts.attrib.pop(qn(attr), None)
    for attr in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
        fonts.set(qn(attr), FONT)


def set_margins(section):
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2.5)
    section.left_margin, section.right_margin = Cm(3.5), Cm(2.5)
    section.footer_distance = Cm(1.25)


def cover_border(section):
    borders = OxmlElement('w:pgBorders')
    borders.set(qn('w:offsetFrom'), 'text')
    for edge in ('top', 'left', 'bottom', 'right'):
        e = OxmlElement(f'w:{edge}')
        e.set(qn('w:val'), 'thinThickSmallGap')
        e.set(qn('w:sz'), '24')
        e.set(qn('w:space'), '18')
        e.set(qn('w:color'), '000000')
        borders.append(e)
    pg_mar = section._sectPr.find(qn('w:pgMar'))
    pg_mar.addnext(borders)


def centered(doc, text, size, bold=False, before=0, after=0):
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = para.paragraph_format
    fmt.first_line_indent = Cm(0)
    fmt.space_before, fmt.space_after, fmt.line_spacing = Pt(before), Pt(after), 1.15
    if text:
        set_font(para.add_run(text), size, bold)
    return para


def cover(doc):
    centered(doc, 'BỘ CÔNG THƯƠNG', 13)
    centered(doc, 'TRƯỜNG ĐẠI HỌC CÔNG THƯƠNG TP. HCM', 13, bold=True, before=4)
    centered(doc, 'KHOA CÔNG NGHỆ THÔNG TIN', 13, bold=True, before=4)
    centered(doc, '-----oOo-----', 13, before=4, after=10)
    logo = centered(doc, '', 13)
    logo.add_run().add_picture(str(LOGO), width=Cm(3.5))
    centered(doc, 'BÁO CÁO TIẾN ĐỘ KHÓA LUẬN', 16, bold=True, before=54, after=24)
    for line in TOPIC_LINES:
        centered(doc, line, 20, bold=True, after=2)
    centered(doc, 'Ngành: Công Nghệ Thông Tin', 16, before=8)
    centered(doc, 'GIẢNG VIÊN HƯỚNG DẪN:', 14, bold=True, before=36)
    centered(doc, ADVISOR, 14, bold=True, before=4)
    centered(doc, 'SINH VIÊN THỰC HIỆN:', 14, bold=True, before=30)
    for i, student in enumerate(STUDENTS, 1):
        para = centered(doc, '', 14, before=4)
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        para.paragraph_format.left_indent = Cm(3.3)
        set_font(para.add_run(f'{i}. {student}'), 14)
    centered(doc, DATE_LINE, 14, before=56)


def page_number_footer(section):
    section.footer.is_linked_to_previous = False
    para = section.footer.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run()
    set_font(run, 13)
    for tag, text in (('begin', None), (None, 'PAGE'), ('end', None)):
        if tag:
            el = OxmlElement('w:fldChar')
            el.set(qn('w:fldCharType'), tag)
        else:
            el = OxmlElement('w:instrText')
            el.set(qn('xml:space'), 'preserve')
            el.text = text
        run._r.append(el)
    num = OxmlElement('w:pgNumType')
    num.set(qn('w:start'), '1')
    section._sectPr.append(num)


def table_borders(table):
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'bottom', 'insideH'):
        e = OxmlElement(f'w:{edge}')
        e.set(qn('w:val'), 'single')
        e.set(qn('w:sz'), '4')
        e.set(qn('w:color'), '000000')
        borders.append(e)
    for edge in ('left', 'right', 'insideV'):
        e = OxmlElement(f'w:{edge}')
        e.set(qn('w:val'), 'nil')
        borders.append(e)
    table._tbl.tblPr.append(borders)


def add_table(doc, headers, rows, widths, align):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table_borders(table)
    alignment = {'L': WD_ALIGN_PARAGRAPH.LEFT, 'C': WD_ALIGN_PARAGRAPH.CENTER}
    for r, values in enumerate([headers] + rows):
        cells = table.rows[0].cells if r == 0 else table.add_row().cells
        tr_pr = table.rows[r]._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement('w:cantSplit'))
        if r == 0:
            tr_pr.append(OxmlElement('w:tblHeader'))
        for j, value in enumerate(values):
            cell = cells[j]
            cell.width = Cm(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER if r == 0 else alignment[align[j]]
            fmt = para.paragraph_format
            fmt.first_line_indent = Cm(0)
            fmt.space_before = fmt.space_after = Pt(3)
            fmt.line_spacing = 1.0
            set_font(para.add_run(str(value)), 13, bold=r == 0)
    for column, width in zip(table.columns, widths):
        column.width = Cm(width)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = 1.0


def word(content: list[tuple], path: Path) -> None:
    doc = Document()
    normal = doc.styles['Normal']
    style_fonts(normal, 13)
    fmt = normal.paragraph_format
    fmt.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    fmt.line_spacing = 1.3
    fmt.space_before, fmt.space_after = Pt(0), Pt(6)
    fmt.first_line_indent = Cm(0.635)
    for name, size in (('Heading 1', 14), ('Heading 2', 13)):
        style = doc.styles[name]
        style_fonts(style, size, bold=True)
        hf = style.paragraph_format
        hf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        hf.first_line_indent = Cm(0)
        hf.space_before, hf.space_after = Pt(12 if name == 'Heading 1' else 6), Pt(6)
        hf.line_spacing = 1.3
        hf.keep_with_next = True
    doc.core_properties.title = 'Báo cáo tiến độ khóa luận KLCN029'
    doc.core_properties.author = 'Nhóm sinh viên KLCN029'

    first = doc.sections[0]
    set_margins(first)
    cover_border(first)
    cover(doc)

    body = doc.add_section(WD_SECTION.NEW_PAGE)
    set_margins(body)
    copied_border = body._sectPr.find(qn('w:pgBorders'))
    if copied_border is not None:
        body._sectPr.remove(copied_border)
    page_number_footer(body)
    centered(doc, 'BÁO CÁO TIẾN ĐỘ THỰC HIỆN KHÓA LUẬN', 18, bold=True, after=12)

    for block in content:
        kind = block[0]
        if kind == 'heading':
            text = block[2].upper() if block[1] == 1 else block[2]
            heading = doc.add_heading('', block[1])
            set_font(heading.add_run(text), 14 if block[1] == 1 else 13, bold=True)
        elif kind == 'paragraph':
            set_font(doc.add_paragraph().add_run(block[1]))
        elif kind == 'bullet':
            para = doc.add_paragraph()
            pf = para.paragraph_format
            pf.left_indent, pf.first_line_indent = Cm(1.27), Cm(-0.635)
            pf.tab_stops.add_tab_stop(Cm(1.27))
            set_font(para.add_run('−\t' + block[1]))
            if block[2]:
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                para.add_run().add_break()
                set_font(para.add_run(block[2]), 11, italic=True)
        elif kind == 'caption':
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf = para.paragraph_format
            pf.first_line_indent = Cm(0)
            pf.space_before, pf.keep_with_next = Pt(6), True
            set_font(para.add_run(block[1]), italic=True)
        else:
            add_table(doc, *block[1:])
    doc.save(path)


if __name__ == '__main__':
    content = blocks()
    (OUT / f'{STEM}.md').write_text(markdown(content), encoding='utf-8')
    word(content, OUT / f'{STEM}.docx')
    print(json.dumps({s: hashlib.sha256((OUT / f'{STEM}{s}').read_bytes()).hexdigest()[:16] for s in ('.md', '.docx')}))
