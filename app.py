from flask import Flask, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import os

# ========= 使用内置日文字体（不用上传任何 otf） =========
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))   # ゴシック体
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))     # 明朝体
# ======================================================

app = Flask(__name__, static_url_path="", static_folder="public")

PAGE_W, PAGE_H = A4
ASSETS_DIR = os.path.join(app.static_folder, "assets")


# 工具：等比铺满（可裁切）的背景
def draw_full_background(p, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    iw, ih = img.getSize()

    # 等比放大到至少覆盖整页
    scale = max(PAGE_W / iw, PAGE_H / ih)
    dw, dh = iw * scale, ih * scale
    x = (PAGE_W - dw) / 2
    y = (PAGE_H - dh) / 2

    p.drawImage(img, x, y, width=dw, height=dh, mask="auto")


# 工具：在指定页面中间画星盘底图
def draw_chart_base(p, size=260):
    path = os.path.join(ASSETS_DIR, "chart_base.png")
    img = ImageReader(path)
    x = (PAGE_W - size) / 2
    y = (PAGE_H - size) / 2
    p.drawImage(img, x, y, width=size, height=size, mask="auto")


@app.route("/")
def root():
    return "astro-report PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# 🔥 之前的纯文字字体测试接口：还保留着，以防要回头排查
@app.route("/api/clean_test", methods=["GET"])
def clean_test_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    p.setFont("HeiseiMin-W3", 24)
    p.drawString(80, PAGE_H - 80, "恋愛占星レポート")

    p.setFont("HeiseiKakuGo-W5", 18)
    p.drawString(80, PAGE_H - 120, "日本語フォントのクリーンテスト")

    p.setFont("HeiseiKakuGo-W5", 14)
    p.drawString(80, PAGE_H - 160, "このPDFに黒い四角の記号が見えなければ、フォントは正常です。")
    p.drawString(80, PAGE_H - 180, "漢字・ひらがな・カタカナだけが表示されているか確認してください。")

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="clean_test.pdf",
                     mimetype="application/pdf")


# ⭐ 正式：demo 版 /api/generate_report（GET）
@app.route("/api/generate_report", methods=["GET"])
def generate_report_demo():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # ---------- 1. 封面 cover.jpg ----------
    draw_full_background(p, "cover.jpg")

    p.setFont("HeiseiMin-W3", 26)
    p.drawString(90, 640, "恋愛占星レポート")

    p.setFont("HeiseiKakuGo-W5", 14)
    p.drawString(90, 610, "サンプルレポート（テスト版）")
    p.drawString(90, 580, "作成日：2025-01-01")  # 之后我们会改成自动日期

    p.showPage()

    # ---------- 2. 目录 / このレポートについて index.jpg ----------
    draw_full_background(p, "index.jpg")

    p.setFont("HeiseiKakuGo-W5", 16)
    p.drawString(90, PAGE_H - 120, "このページはテンプレート背景のテストです。")
    p.drawString(90, PAGE_H - 140, "画像の位置やトリミングが問題なければ OK です。")

    p.showPage()

    # ---------- 3. 基本ホロスコープ page_basic.jpg + 星盤底图 ----------
    draw_full_background(p, "page_basic.jpg")

    p.setFont("HeiseiKakuGo-W5", 18)
    p.drawString(90, PAGE_H - 120, "基本ホロスコープと総合相性（サンプル）")

    # 在中间画 chart_base.png
    draw_chart_base(p, size=260)

    p.setFont("HeiseiKakuGo-W5", 12)
    p.drawString(90, 180, "※ 今は星の位置はまだ固定イラストです。後で自動計算を組み込みます。")

    p.showPage()

    # ---------- 4. 性格の違いとコミュニケーション ----------
    draw_full_background(p, "page_communication.jpg")
    p.setFont("HeiseiKakuGo-W5", 16)
    p.drawString(90, PAGE_H - 120, "ここにはコミュニケーションに関する文章が入ります。（デモ）")
    p.showPage()

    # ---------- 5. 相性の良い点・すれ違いやすい点 ----------
    draw_full_background(p, "page_points.jpg")
    p.setFont("HeiseiKakuGo-W5", 16)
    p.drawString(90, PAGE_H - 120, "ここには相性のポイントに関する文章が入ります。（デモ）")
    p.showPage()

    # ---------- 6. 関係の方向性と今後の傾向 ----------
    draw_full_background(p, "page_trend.jpg")
    p.setFont("HeiseiKakuGo-W5", 16)
    p.drawString(90, PAGE_H - 120, "ここには関係の流れ・今後の傾向が入ります。（デモ）")
    p.showPage()

    # ---------- 7. 日常で役立つアドバイス ----------
    draw_full_background(p, "page_advice.jpg")
    p.setFont("HeiseiKakuGo-W5", 16)
    p.drawString(90, PAGE_H - 120, "ここには日常で役立つアドバイスの文章が入ります。（デモ）")
    p.showPage()

    # ---------- 8. まとめ ----------
    draw_full_background(p, "page_summary.jpg")
    p.setFont("HeiseiMin-W3", 20)
    p.drawString(90, PAGE_H - 120, "まとめ（サンプル）")

    p.setFont("HeiseiKakuGo-W5", 14)
    p.drawString(90, PAGE_H - 160, "本レポートは、テンプレートとフォントの動作確認用デモです。")
    p.drawString(90, PAGE_H - 180, "星の計算ロジックと個別の文章生成は、このあと段階的に組み込んでいきます。")

    p.showPage()

    # ---------- 完成 ----------
    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="love_report_demo.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
