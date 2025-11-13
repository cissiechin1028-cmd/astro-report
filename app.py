# -*- coding: utf-8 -*-
from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

import io
import os
from datetime import datetime

# --------------------------------------------------
# Flask 基本设置（保持你之前的静态文件结构）
# --------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
ASSETS_DIR = os.path.join(PUBLIC_DIR, "assets")

# --------------------------------------------------
# 注册你上传的日文字体（Noto Sans JP 系列）
# --------------------------------------------------
def register_fonts():
    try:
        pdfmetrics.registerFont(
            TTFont("NotoSansJP-Regular",
                   os.path.join(ASSETS_DIR, "NotoSansJP-Regular.otf"))
        )
        pdfmetrics.registerFont(
            TTFont("NotoSansJP-Medium",
                   os.path.join(ASSETS_DIR, "NotoSansJP-Medium.otf"))
        )
        pdfmetrics.registerFont(
            TTFont("NotoSansJP-Bold",
                   os.path.join(ASSETS_DIR, "NotoSansJP-Bold.otf"))
        )
    except Exception as e:
        # 出问题也先不让程序崩，方便日志排查
        print("Font register error:", e)

register_fonts()

# --------------------------------------------------
# 小工具：画全屏背景图
# --------------------------------------------------
def draw_full_background(c, img_path, page_width, page_height):
    if not os.path.exists(img_path):
        return

    img = ImageReader(img_path)
    iw, ih = img.getSize()

    # 按比例铺满 A4
    scale = min(page_width / float(iw), page_height / float(ih))
    draw_w = iw * scale
    draw_h = ih * scale
    x = (page_width - draw_w) / 2.0
    y = (page_height - draw_h) / 2.0

    c.drawImage(img, x, y, width=draw_w, height=draw_h)

# --------------------------------------------------
# 根路径 & test.html 保持原样
# --------------------------------------------------
@app.route('/')
def root():
    return "PDF server running."

@app.route('/test.html')
def test_page():
    return app.send_static_file('test.html')

# --------------------------------------------------
# 生成 PDF 报告
# GET /api/generate_report?male_name=太郎&female_name=花子&date=2025-01-01
# --------------------------------------------------
@app.route('/api/generate_report', methods=['GET'])
def generate_report():
    # -------- 参数处理（留默认值，方便你直接访问测试） --------
    male_name = request.args.get('male_name', '太郎')
    female_name = request.args.get('female_name', '花子')

    # date: 2025-01-01 -> 2025年01月01日
    date_str = request.args.get('date')
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            dt = datetime.today()
    else:
        dt = datetime.today()
    display_date = dt.strftime("%Y年%m月%d日")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    # --------------------------------------------------
    # 1. 封面页（只在指定位置加姓名 + 作成日）
    # --------------------------------------------------
    cover_path = os.path.join(ASSETS_DIR, "cover.jpg")
    draw_full_background(c, cover_path, page_width, page_height)

    # ① 姓名：太郎 さん ＆ 花子 さん
    # 大概位置：背景大标题「恋愛占星レポート」的上方一点，居中
    names_line = f"{male_name} さん ＆ {female_name} さん"
    c.setFont("NotoSansJP-Bold", 20)
    name_text_w = pdfmetrics.stringWidth(names_line, "NotoSansJP-Bold", 20)
    name_x = (page_width - name_text_w) / 2.0
    # 这个 y 值是靠目测定的，如需微调你可以改这里
    name_y = page_height * 0.66
    c.drawString(name_x, name_y, names_line)

    # ② 作成日：2025年01月01日
    date_line = f"作成日：{display_date}"
    c.setFont("NotoSansJP-Regular", 12)
    date_text_w = pdfmetrics.stringWidth(date_line, "NotoSansJP-Regular", 12)
    date_x = (page_width - date_text_w) / 2.0
    # 放在页面底部留白区域中间
    date_y = page_height * 0.11
    c.drawString(date_x, date_y, date_line)

    c.showPage()

    # --------------------------------------------------
    # 2. このレポートについて / 目次 页（index.jpg）
    #    这里只放背景 + 一段说明文字，避开标题区域
    # --------------------------------------------------
    index_path = os.path.join(ASSETS_DIR, "index.jpg")
    draw_full_background(c, index_path, page_width, page_height)

    c.setFont("NotoSansJP-Regular", 11)
    text = "※ このページはテンプレート確認用のサンプルです。"
    c.drawString(80, page_height * 0.22, text)

    c.showPage()

    # --------------------------------------------------
    # 3. 基本ホロスコープと総合相性ページ
    #    → ここで「星盤を左右に２つ」＋ 名前
    # --------------------------------------------------
    basic_bg = os.path.join(ASSETS_DIR, "page_basic.jpg")
    chart_img_path = os.path.join(ASSETS_DIR, "chart_base.png")
    draw_full_background(c, basic_bg, page_width, page_height)

    if os.path.exists(chart_img_path):
        chart_img = ImageReader(chart_img_path)
        iw, ih = chart_img.getSize()

        # 星盘目标尺寸：不要超过白色半透明区域
        target_diameter = page_width * 0.28  # 约 30% 宽度
        scale = target_diameter / float(max(iw, ih))
        chart_w = iw * scale
        chart_h = ih * scale

        # 星盘纵向位置（大概在页面高度中部略偏上）
        chart_y = page_height * 0.33

        # 左右位置
        left_x = page_width * 0.16
        right_x = page_width * 0.56

        # 左：男性
        c.drawImage(
            chart_img,
            left_x,
            chart_y,
            width=chart_w,
            height=chart_h,
            mask='auto'
        )

        # 右：女性
        c.drawImage(
            chart_img,
            right_x,
            chart_y,
            width=chart_w,
            height=chart_h,
            mask='auto'
        )

        # 星盘下方姓名标签
        c.setFont("NotoSansJP-Regular", 12)

        left_label = f"{male_name} さんのホロスコープ"
        lw = pdfmetrics.stringWidth(left_label, "NotoSansJP-Regular", 12)
        c.drawString(left_x + (chart_w - lw) / 2.0, chart_y - 22, left_label)

        right_label = f"{female_name} さんのホロスコープ"
        rw = pdfmetrics.stringWidth(right_label, "NotoSansJP-Regular", 12)
        c.drawString(right_x + (chart_w - rw) / 2.0, chart_y - 22, right_label)

        # 页面底部的小提示
        c.setFont("NotoSansJP-Regular", 9)
        hint = "※ 星の位置は現在ダミーのイラストです。後で自動計算ロジックを組み込みます。"
        c.drawString(80, page_height * 0.13, hint)

    c.showPage()

    # --------------------------------------------------
    # 4. 性格の違いとコミュニケーション（page_communication）
    # --------------------------------------------------
    comm_bg = os.path.join(ASSETS_DIR, "page_communication.jpg")
    draw_full_background(c, comm_bg, page_width, page_height)

    c.setFont("NotoSansJP-Regular", 11)
    c.drawString(80, page_height * 0.22,
                 "ここには性格・コミュニケーションに関する文章が入ります。（サンプル）")

    c.showPage()

    # --------------------------------------------------
    # 5. 相性の良い点・すれ違いやすい点（page_points）
    # --------------------------------------------------
    points_bg = os.path.join(ASSETS_DIR, "page_points.jpg")
    draw_full_background(c, points_bg, page_width, page_height)

    c.setFont("NotoSansJP-Regular", 11)
    c.drawString(80, page_height * 0.22,
                 "ここには相性ポイントに関する文章が入ります。（サンプル）")

    c.showPage()

    # --------------------------------------------------
    # 6. 関係の方向性と今後の傾向（page_trend）
    # --------------------------------------------------
    trend_bg = os.path.join(ASSETS_DIR, "page_trend.jpg")
    draw_full_background(c, trend_bg, page_width, page_height)

    c.setFont("NotoSansJP-Regular", 11)
    c.drawString(80, page_height * 0.22,
                 "ここには関係の流れや今後の傾向に関する文章が入ります。（サンプル）")

    c.showPage()

    # --------------------------------------------------
    # 7. 日常で役立つアドバイス（page_advice）
    # --------------------------------------------------
    advice_bg = os.path.join(ASSETS_DIR, "page_advice.jpg")
    draw_full_background(c, advice_bg, page_width, page_height)

    c.setFont("NotoSansJP-Regular", 11)
    c.drawString(80, page_height * 0.22,
                 "ここには日常で役立つアドバイスの文章が入ります。（サンプル）")

    c.showPage()

    # --------------------------------------------------
    # 8. まとめ（page_summary）
    # --------------------------------------------------
    summary_bg = os.path.join(ASSETS_DIR, "page_summary.jpg")
    draw_full_background(c, summary_bg, page_width, page_height)

    c.setFont("NotoSansJP-Regular", 11)
    c.drawString(80, page_height * 0.26,
                 "このレポートは、西洋占星術のホロスコープ解析と心理傾向データをもとに作成した内容です。")
    c.drawString(80, page_height * 0.23,
                 "結果は運命を決めるものではなく、おふたりがより深く理解し合い、穏やかな気持ちで愛を育むための小さな指針です。")

    c.showPage()

    # --------------------------------------------------
    # 收尾 & 返回 PDF
    # --------------------------------------------------
    c.save()
    buffer.seek(0)

    filename = f"love_report_{male_name}_{female_name}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# --------------------------------------------------
# 本地调试用（Render 上不会用到）
# --------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
