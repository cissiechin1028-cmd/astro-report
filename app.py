from flask import Flask, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io

# ========= 使用内置日文字体（不用上传任何 otf） =========
# 无衬线：ゴシック体
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
# 有衬线：明朝体（备用）
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
# ======================================================

app = Flask(__name__, static_url_path='', static_folder='public')


@app.route('/')
def root():
    return "PDF server running."


@app.route('/test.html')
def test_page():
    return app.send_static_file('test.html')


@app.route('/api/generate_report', methods=['GET'])
def generate_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # 标题：明朝体
    p.setFont("HeiseiMin-W3", 24)
    p.drawString(80, 780, "恋愛占星レポート")

    # 小标题：ゴシック体
    p.setFont("HeiseiKakuGo-W5", 18)
    p.drawString(80, 740, "フォントテスト：日本語がちゃんと表示されるか確認します。")

    # 正文：ゴシック体
    p.setFont("HeiseiKakuGo-W5", 14)
    p.drawString(80, 700, "これは ReportLab 内蔵フォントを使った日本語テストです。")
    p.drawString(80, 680, "ブラックボックス（■■■）ではなく、漢字・ひらがな・カタカナが見えれば成功です。")

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
