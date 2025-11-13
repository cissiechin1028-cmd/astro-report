from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.utils import ImageReader

import io
import datetime

# -------------------------------------------------
# Flask 基本设置：public 作为静态目录
# -------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

# 注册 ReportLab 自带的日文字体（不依赖你的 .otf/.ttf）
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))   # 明朝体：标题
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))  # 角ゴ：正文


# -------------------------------------------------
# 根路径 & 静态测试页
# -------------------------------------------------
@app.route('/')
def root():
    return "PDF server running."

@app.route('/test.html')
def test_page():
    return app.send_static_file('test.html')


# -------------------------------------------------
# 封面绘制
# -------------------------------------------------
def draw_cover(c, male_name, female_name, report_date):
    """
    封面：
      - 背景：cover.jpg
      - 姓名：放在「恋愛占星レポート」上方（大概居中偏上）
      - 作成日：底部中间，格式：作成日：YYYY年MM月DD日
    """
    width, height = A4

    # 背景封面图
    cover_img = ImageReader("public/assets/cover.jpg")
    c.drawImage(cover_img, 0, 0, width=width, height=height)

    # 姓名行：太郎 さん ＆ 花子 さん
    title_font = "HeiseiMin-W3"
    title_size = 20
    c.setFont(title_font, title_size)
    c.setFillColorRGB(0, 0, 0)

    name_text = f"{male_name} さん ＆ {female_name} さん"
    name_width = pdfmetrics.stringWidth(name_text, title_font, title_size)

    # 粗略放在封面大标题「恋愛占星レポート」上方一点
    name_y = height * 0.68  # 需要的话你可以微调这个比例
    c.drawString((width - name_width) / 2, name_y, name_text)

    # 作成日：YYYY年MM月DD日
    date_font = "HeiseiKakuGo-W5"
    date_size = 12
    c.setFont(date_font, date_size)

    date_text = f"作成日：{report_date.year}年{report_date.month:02d}月{report_date.day:02d}日"
    date_width = pdfmetrics.stringWidth(date_text, date_font, date_size)

    # 放在页面底部中间，略高于边缘，覆盖住原来的「作成日： 年 月 日」
    date_y = 80  # 如果位置偏上/偏下，你只改这个数字就行
    c.drawString((width - date_width) / 2, date_y, date_text)

    c.showPage()


# -------------------------------------------------
# 星盘双图页面
# -------------------------------------------------
def draw_chart_page(c, male_name, female_name):
    """
    星盘页：
      - 背景：page_basic.jpg
      - 星盘图：chart_base.png，一左一右
      - 星盘下方加姓名
    """
    width, height = A4

    # 背景
    bg = ImageReader("public/assets/page_basic.jpg")
    c.drawImage(bg, 0, 0, width=width, height=height)

    # 星盘图片
    chart_img = ImageReader("public/assets/chart_base.png")

    # 星盘大小（根据白色区域大致估一个，不要超出）
    chart_size = 230  # 你觉得太大/太小可以以后再改

    # 左右位置（中心点）
    left_x = width * 0.22
    right_x = width * 0.72
    center_y = height * 0.50

    # 画左侧星盘
    c.drawImage(
        chart_img,
        left_x - chart_size / 2,
        center_y - chart_size / 2,
        width=chart_size,
        height=chart_size,
        mask='auto'
    )

    # 画右侧星盘
    c.drawImage(
        chart_img,
        right_x - chart_size / 2,
        center_y - chart_size / 2,
        width=chart_size,
        height=chart_size,
        mask='auto'
    )

    # 姓名（星盘下）
    c.setFont("HeiseiKakuGo-W5", 12)
    c.setFillColorRGB(0, 0, 0)

    c.drawCentredString(left_x, center_y - chart_size / 2 - 18, f"{male_name} さん")
    c.drawCentredString(right_x, center_y - chart_size / 2 - 18, f"{female_name} さん")

    c.showPage()


# -------------------------------------------------
# 其他整页 JPG（说明/目录/性格/相性/趋势/建议/总结）
# 只铺背景，不再盖标题
# -------------------------------------------------
def draw_static_fullpage(c, filename):
    width, height = A4
    img = ImageReader(f"public/assets/{filename}")
    c.drawImage(img, 0, 0, width=width, height=height)
    c.showPage()


# -------------------------------------------------
# 生成 PDF 主入口
# -------------------------------------------------
@app.route('/api/generate_report', methods=['GET'])
def generate_pdf():
    """
    生成恋爱占星 PDF 报告（测试版）

    可选参数（GET）：
      - male_name   （默认：太郎）
      - female_name （默认：花子）
      - report_date （默认：今天，格式：YYYY-MM-DD 或 YYYY/MM/DD）
    """
    # 1) 获取参数
    male_name = request.args.get('male_name', '太郎').strip() or '太郎'
    female_name = request.args.get('female_name', '花子').strip() or '花子'

    date_str = request.args.get('report_date', '').strip()
    if date_str:
        try:
            date_str_norm = date_str.replace('/', '-').replace('.', '-')
            y, m, d = [int(x) for x in date_str_norm.split('-')]
            report_date = datetime.date(y, m, d)
        except Exception:
            report_date = datetime.date.today()
    else:
        report_date = datetime.date.today()

    # 2) 创建 PDF 缓冲区
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # 3) 封面
    draw_cover(c, male_name, female_name, report_date)

    # 4) 目录页（整页 JPG）
    draw_static_fullpage(c, "index.jpg")

    # 5) 星盘双图页
    draw_chart_page(c, male_name, female_name)

    # 6) 其余静态页面（按你素材的顺序来）
    static_pages = [
        "page_basic.jpg",          # 说明页 or 其他
        "page_points.jpg",         # 相性ポイント
        "page_communication.jpg",  # コミュニケーション
        "page_trend.jpg",          # 今後の傾向
        "page_advice.jpg",         # 日常のアドバイス
        "page_summary.jpg",        # まとめ
    ]

    for fn in static_pages:
        draw_static_fullpage(c, fn)

    # 结束 PDF
    c.save()
    buffer.seek(0)

    filename = "love_report_sample.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


if __name__ == '__main__':
    # 本地测试用，Render 上不会走到这里
    app.run(host='0.0.0.0', port=10000)
