from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

# ========  注册日文字体（你上传的那三个）  ========
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("NotoSansJP-Regular", "public/assets/NotoSansJP-Regular.otf"))
pdfmetrics.registerFont(TTFont("NotoSansJP-Medium", "public/assets/NotoSansJP-Medium.otf"))
pdfmetrics.registerFont(TTFont("NotoSansJP-Bold", "public/assets/NotoSansJP-Bold.otf"))

FONT_REGULAR = "NotoSansJP-Regular"
FONT_MEDIUM  = "NotoSansJP-Medium"
FONT_BOLD    = "NotoSansJP-Bold"

# ================================================

app = Flask(__name__, static_url_path='', static_folder='public')


# ---- 根路径，避免 Render 显示 404 ----
@app.route('/')
def root():
    return "PDF server running."


# ---- 静态文件测试页面 ----
@app.route('/test.html')
def test_page():
    return app.send_static_file('test.html')


# ---- PDF 生成测试（已使用日语字体） ----
@app.route('/api/generate_report', methods=['GET'])
def generate_pdf():

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # 测试内容
    p.setFont(FONT_BOLD, 24)
    p.drawString(80, 780, "恋愛占星レポート")

    p.setFont(FONT_MEDIUM, 18)
    p.drawString(80, 740, "フォントテスト：日本語は正常に表示されます。")

    p.setFont(FONT_REGULAR, 14)
    p.drawString(80, 700, "これは NotoSansJP-Regular を使用した本文テストです。")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="test.pdf",
        mimetype='application/pdf'
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
