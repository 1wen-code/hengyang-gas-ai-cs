"""FAQ和法规知识库 CSV -> PDF附件"""
import pandas as pd
from fpdf import FPDF

FONT = r'C:/Windows/Fonts/simhei.ttf'

class PDF(FPDF):
    def __init__(self, title):
        super().__init__('L', 'mm', 'A4')
        self.t = title
        self.set_auto_page_break(True, 15)
        self.add_font('zh', '', FONT)
        self.add_font('zh', 'B', FONT)
        self.add_font('zh', 'I', FONT)

    def header(self):
        self.set_font('zh', 'B', 11)
        self.cell(0, 8, self.t, align='C', new_x='LMARGIN', new_y='NEXT')
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-12); self.set_font('zh', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

def csv_to_pdf(csv_path, pdf_path, title):
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    cols = list(df.columns)
    rows = df.values.tolist()
    n_cols = len(cols)

    pdf = PDF(title)
    pdf.alias_nb_pages()
    pdf.add_page()

    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    col_w = []
    for i, col in enumerate(cols):
        mx = len(str(col))
        for r in rows[:60]:
            mx = max(mx, len(str(r[i])) if pd.notna(r[i]) else 0)
        col_w.append(min(mx * 2.0 + 5, page_w * 0.5))
    total = sum(col_w)
    if total > page_w:
        s = page_w / total; col_w = [w*s for w in col_w]
    if total < page_w:
        extra = (page_w - total) / n_cols; col_w = [w+extra for w in col_w]

    pdf.set_fill_color(30,30,50); pdf.set_text_color(255,255,255)
    pdf.set_font('zh', 'B', 7)
    for i,c in enumerate(cols):
        pdf.cell(col_w[i], 7, str(c), border=1, fill=True, align='C')
    pdf.ln()

    pdf.set_text_color(0,0,0); pdf.set_font('zh', '', 6.5)
    for ri, row in enumerate(rows):
        pdf.set_fill_color(245,245,250) if ri%2==0 else pdf.set_fill_color(255,255,255)
        row_h = 5
        for i,val in enumerate(row):
            text = str(val) if pd.notna(val) else ''
            if len(text) > 30: row_h = max(row_h, 7)
        for i,val in enumerate(row):
            text = str(val) if pd.notna(val) else ''
            pdf.cell(col_w[i], row_h, text[:250], border=1, fill=True, align='L')
        pdf.ln()

    pdf.output(pdf_path)
    print(f'{pdf_path}  ({len(rows)} rows)')

csv_to_pdf(
    r'C:/Users/wenju/OneDrive/文档/faq_knowledge.csv',
    r'C:/Users/wenju/OneDrive/文档/FAQ知识库附件.pdf',
    'FAQ知识库（1009条）'
)

csv_to_pdf(
    r'C:/Users/wenju/OneDrive/文档/policy_knowledge.csv',
    r'C:/Users/wenju/OneDrive/文档/法规知识库附件.pdf',
    '法规知识库（72条）'
)
