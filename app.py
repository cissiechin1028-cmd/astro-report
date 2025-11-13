from flask import Flask, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import io
import os

from PIL import Image, ImageDraw, ImageFont   # 用来把日文画成图片

app = Flask(__name__, static_url_path='', static_folder='public')

# ========= 根据日文字符串生成一张 PNG 图片（透明底） =========
def make_text_image(text, font_size=32, max_width=1000):
    """
    把日文文本画到一张透明 PNG 里，返回 BytesIO（给 ReportLab 用）
    """
    assets_dir = os.path.join(app.static_folder, "assets")
    # 用你已经上传的 NotoSansJP-Regular.otf（如果没有就改成实际文件名）
    font_path = os.path.join(assets_dir, "NotoSansJP-Regular.otf")

    # 先随便开一张大画布，算宽高
    tmp_img = Image.new("RGBA", (max_width, font_size * 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tmp_img)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        # 如果加载失败，就退回系统默认字体（效果差一些，但不会报错）
        font = ImageFont.load_default()

    # 支持多行
    lines = text.split("\n")
    line_heights = []
    max_line_width = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_line_width = max(max_line_width, w)
        line_heights.append(h)

    total_height = sum(line_heights) + (len(lines) - 1) * int(font_size * 0.4)

    # 真正大小的画布
    img = Image.new("RGBA", (max_line_width + 10, total_height + 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = 0
    for i, line in enumerate(lines):
        draw.text((0, y), line, font=font, fill=(0, 0, 0, 255))
        y += line_heights[i] + int(font_size * 0.4)

    # 保存到内存
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# =========================================================


@app.route("/")
def root():
    return "PDF server running (image-based Japanese text)."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


@app.route("/api/generate_report", methods=["GET"])
def generate_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # 1. 标题图片（大号）
    title_text = "恋愛占星レポート"
    title_img_buf = make_text_image(title_text, font_size=36)
    title_img = ImageReader(title_img_buf)

    # 2. 副标题 / 说明（中号，多行）
    sub_text = "フォントテスト：\n日本語が黒い四角ではなく、\nちゃんと読める文字になっていれば成功です。"
    sub_img_buf = make_text_image(sub_text, font_size=18)
    sub_img = ImageReader(sub_img_buf)

    # 把图片画到 PDF 上（坐标用 pt）
    # 标题放上方
    p.drawImage(title_img, 80, height - 120, mask="auto")
    # 副标题放下面一点
    p.drawImage(sub_img, 80, height - 260, mask="auto")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="test.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
