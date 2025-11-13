from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os

app = Flask(__name__, static_url_path='', static_folder='public')

# ====== 注册日文字体（必须放在 public/assets 下） ======
BASE_PATH = os.path.join(app.static_folder, "assets")

FONT_REGULAR = os.path.join(BASE_PATH, "NotoSansJP-Regular.otf")
FONT_MEDIUM = os.path.join(BASE_PATH, "NotoSansJP-Medium.otf")
FONT_BOLD = os.path.join(BASE_PATH, "NotoSansJP-Bold.otf")

pdfmetrics.registerFont(TTFont("NotoSansJP", FONT_REGULAR))
pdfmetrics.registerFont(TTFont("NotoSansJP-Medium", FONT_MEDIUM))
pdfmetrics.registerFont(TTFont("NotoSansJP-Bold", FONT_BOLD))

# ====== 根路径 ======
@app.route('/')
def root():
    return "PDF server running."

# ====== 静态 test 页面 ======
@app.route('/test.html')
def test_page():
    return app.send_static_file('test.html')

# ====== 生成 PDF ======
@app.route('/api/generate_report', methods=['GET'])
def generate_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # 使用日本語字体
    p.setFont("NotoSansJP", 24)
    p.drawString(100, 780, "PDF 日本語テスト成功！")
    p.drawString(100, 740, "恋愛占星レポートの日本語も正しく表示できます。")

    p.setFont("NotoSansJP-Bold", 28)
    p.drawString(100, 700, "→ これは太字（Bold）です")

    p.setFont("NotoSansJP-Medium", 20)
    p.drawString(100, 660, "→ これは Medium（中等太さ）です")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="test.pdf",
        mimetype="application/pdf"
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
