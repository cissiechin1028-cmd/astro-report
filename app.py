from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import os
import datetime
import math

import json

# Token 使用次数记录文件
TOKEN_FILE = "token_usage.json"

def load_token_usage():
    if not os.path.exists(TOKEN_FILE):
        return {}
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_token_usage(data):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def token_remaining(token):
    data = load_token_usage()
    count = data.get(token, 0)
    # 最多 3 次
    return max(0, 3 - count)


# ------------------------------------------------------------------
# Flask 基本设置：public 目录作为静态目录
# ------------------------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4

# ------------------------------------------------------------------
# 字体设置
#   JP_SANS  : 粗一点的黑体（标题用）
#   JP_SERIF : 细一点的明朝体（正文、第三页用）
# ------------------------------------------------------------------
JP_SANS = "HeiseiKakuGo-W5"
JP_SERIF = "HeiseiMin-W3"
pdfmetrics.registerFont(UnicodeCIDFont(JP_SANS))
pdfmetrics.registerFont(UnicodeCIDFont(JP_SERIF))


# ------------------------------------------------------------------
# 小工具：铺满整页背景
# ------------------------------------------------------------------
def draw_full_bg(c, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


# ------------------------------------------------------------------
# 小工具：日期格式化 YYYY-MM-DD → 2025年11月13日
# ------------------------------------------------------------------
def get_display_date(raw_date: str | None) -> str:
    if raw_date:
        try:
            d = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            d = datetime.date.today()
    else:
        d = datetime.date.today()
    return f"{d.year}年{d.month}月{d.day}日"


# ------------------------------------------------------------------
# 小工具：极坐标 → 直角坐标（0° 在 12 点方向，逆时针）
# ------------------------------------------------------------------
def polar_to_xy(cx, cy, radius, angle_deg):
    theta = math.radians(90 - angle_deg)  # 0° 在上
    x = cx + radius * math.cos(theta)
    y = cy + radius * math.sin(theta)
    return x, y


# ------------------------------------------------------------------
# 小工具：在星盘上画「彩色点 + PNG 图标」
# ------------------------------------------------------------------
def draw_planet_icon(
    c,
    cx,
    cy,
    chart_size,
    angle_deg,
    color_rgb,
    icon_filename,
):
    """
    cx, cy      : 星盘中心
    chart_size  : 整个星盘图片的宽高（正方形）
    angle_deg   : 行星度数（0°=白羊 0°，在 12 点）
    color_rgb   : 小圆点颜色 (r, g, b)
    icon_filename : public/assets 下的 PNG 文件名
    """

    # 根据星盘大小估一个“外圈点的半径”和“内圈图标的半径”
    r_dot = chart_size * 0.34   # 彩色点：接近黄道外圈
    r_icon = chart_size * 0.28  # 图标：更靠内圈，不挡星座符号

    # 彩色小圆点位置（外圈）
    px, py = polar_to_xy(cx, cy, r_dot, angle_deg)
    r, g, b = color_rgb
    c.setFillColorRGB(r, g, b)
    c.circle(px, py, 2.3, fill=1, stroke=0)

    # 图标位置（内圈）
    ix, iy = polar_to_xy(cx, cy, r_icon, angle_deg)

    icon_path = os.path.join(ASSETS_DIR, icon_filename)
    icon_img = ImageReader(icon_path)
    icon_size = 11  # PNG 尺寸（可以微调）

    c.drawImage(
        icon_img,
        ix - icon_size / 2,
        iy - icon_size / 2,
        width=icon_size,
        height=icon_size,
        mask="auto",
    )


# ------------------------------------------------------------------
# 小工具：文本自动换行（第 4～6 页通用）
# ------------------------------------------------------------------
def draw_wrapped_block(c, text, x, y_start, wrap_width,
                       font_name, font_size, line_height):
    """
    在 (x, y_start) 开始画一段文字，按字符宽度自动换行。
    返回最后一行画完后的下一行 y 坐标（方便接着往下画）。
    """
    c.setFont(font_name, font_size)
    line = ""
    y = y_start

    for ch in text:
        if ch == "\n":
            # 手动换行
            c.drawString(x, y, line)
            line = ""
            y -= line_height
            continue

        new_line = line + ch
        if pdfmetrics.stringWidth(new_line, font_name, font_size) <= wrap_width:
            line = new_line
        else:
            c.drawString(x, y, line)
            line = ch
            y -= line_height

    if line:
        c.drawString(x, y, line)
        y -= line_height

    return y


# ------------------------------------------------------------------
# 行数限制版：最多画 max_lines 行（第 6 页表格用）
# ------------------------------------------------------------------
def draw_wrapped_block_limited(
    c,
    text,
    x,
    y_start,
    wrap_width,
    font_name,
    font_size,
    line_height,
    max_lines,
):
    """
    在 (x, y_start) 开始画一段文字，自动换行，但最多画 max_lines 行。
    返回最后一行画完后的下一行 y 坐标。
    """
    c.setFont(font_name, font_size)
    line = ""
    y = y_start
    lines = 0

    for ch in text:
        if ch == "\n":
            c.drawString(x, y, line)
            line = ""
            y -= line_height
            lines += 1
            if lines >= max_lines:
                return y
            continue

        new_line = line + ch
        if pdfmetrics.stringWidth(new_line, font_name, font_size) <= wrap_width:
            line = new_line
        else:
            c.drawString(x, y, line)
            line = ch
            y -= line_height
            lines += 1
            if lines >= max_lines:
                return y

    if line and lines < max_lines:
        c.drawString(x, y, line)
        y -= line_height

    return y


# ------------------------------------------------------------------
# 根路径 & test.html
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# ------------------------------------------------------------------
# 生成 PDF 主入口
# ------------------------------------------------------------------
@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # ---- 1. 读取参数 ----
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")
    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    # ---- 2. 准备 PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # ------------------------------------------------------------------
    # 封面：cover.jpg
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名：恋愛占星レポート 正上方（字体颜色整体调浅一点）
    c.setFont(JP_SANS, 18)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(JP_SANS, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 2 页：目录页（index.jpg）
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置（整体稍微缩小：200 → 180）
    chart_size = 180
    left_x = 90
    left_y = 520
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 星盘中心
    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    # 画星盘底图
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # ------------------ 行星示例数据（角度 + 文字） ------------------
    male_planets = {
        "sun":   {"deg": 12.3,  "label": "太陽：牡羊座 12.3°"},
        "moon":  {"deg": 65.4,  "label": "月：双子座 5.4°"},
        "venus": {"deg": 147.8, "label": "金星：獅子座 17.8°"},
        "mars":  {"deg": 183.2, "label": "火星：天秤座 3.2°"},
        "asc":   {"deg": 220.1, "label": "ASC：山羊座 20.1°"},
    }

    female_planets = {
        "sun":   {"deg": 8.5,   "label": "太陽：蟹座 8.5°"},
        "moon":  {"deg": 150.0, "label": "月：乙女座 22.0°"},
        "venus": {"deg": 214.6, "label": "金星：蠍座 14.6°"},
        "mars":  {"deg": 262.9, "label": "火星：水瓶座 2.9°"},
        "asc":   {"deg": 288.4, "label": "ASC：魚座 28.4°"},
    }

    # 与 key 对应的 PNG 文件名
    icon_files = {
        "sun": "icon_sun.png",
        "moon": "icon_moon.png",
        "venus": "icon_venus.png",
        "mars": "icon_mars.png",
        "asc": "icon_asc.png",
    }

    # 男 = 蓝色 / 女 = 粉色
    male_color = (0.15, 0.45, 0.9)
    female_color = (0.9, 0.35, 0.65)

    # ------------------ 在星盘上画点 + 图标（内圈） ------------------
    for key, info in male_planets.items():
        draw_planet_icon(
            c,
            left_cx,
            left_cy,
            chart_size,
            info["deg"],
            male_color,
            icon_files[key],
        )

    for key, info in female_planets.items():
        draw_planet_icon(
            c,
            right_cx,
            right_cy,
            chart_size,
            info["deg"],
            female_color,
            icon_files[key],
        )

    # ------------------ 星盘下方姓名（用细明朝体） ------------------
    c.setFont(JP_SERIF, 14)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # ------------------ 星盘下方 5 行列表（用细明朝体，左对齐） ------------------
    c.setFont(JP_SERIF, 8.5)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    male_lines = [info["label"] for info in male_planets.values()]
    for i, line in enumerate(male_lines):
        y = left_y - 45 - i * 11
        c.drawString(left_cx - 30, y, line)

    female_lines = [info["label"] for info in female_planets.values()]
    for i, line in enumerate(female_lines):
        y = right_y - 45 - i * 11
        c.drawString(right_cx - 30, y, line)

    # ------------------------------------------------------------------
    # 星盘下：総合相性スコア ＋ 太陽・月・上昇の分析
    # ------------------------------------------------------------------
    text_x3 = 130
    wrap_width3 = 360
    body_font3 = JP_SERIF
    body_size3 = 12
    line_height3 = 18

    # ===== 総合相性スコア =====
    compat_score = 82  # ★ 先写死一个分数，之后你可以自己换成计算结果
    c.setFont(JP_SANS, 12)
    c.drawString(text_x3, 350, f"相性バランス： {compat_score} / 100")

    # 俯瞰式总结（最多 2 行）
    compat_summary = (
        "二人の相性は、安心感とほどよい刺激がバランスよく混ざった組み合わせです。"
        "ゆっくりと関係を育てていくほど、お互いの良さが引き出されやすいタイプといえます。"
    )
    draw_wrapped_block_limited(
        c,
        compat_summary,
        text_x3,
        350 - line_height3 * 1.4,  # 标题下留一点空隙
        wrap_width3,
        body_font3,
        body_size3,
        line_height3,
        max_lines=2,
    )

    # ===== 太陽・月・上昇の分析 =====
    y_analysis = 220
    analysis_blocks = [
        (
            "太陽（ふたりの価値観）：",
            "太郎 さんは安定感と責任感を、花子 さんは素直さとあたたかさを大切にするタイプです。"
            "方向性を共有できると、同じゴールに向かって進みやすくなります。"
        ),
        (
            "月（素の感情と安心ポイント）：",
            "太郎 さんは落ち着いた空間やペースを守れる関係に安心し、"
            "花子 さんは気持ちをその場で分かち合えることに心地よさを感じやすい傾向があります。"
        ),
        (
            "ASC（第一印象・ふたりの雰囲気）：",
            "出会ったときの印象は、周りから見ると「穏やかだけれど芯のあるペア」。"
            "少しずつ素の表情が見えるほど、二人らしい雰囲気が育っていきます。"
        ),
    ]

    c.setFont(body_font3, body_size3)

    for title, text in analysis_blocks:
        # 小标题 + 本文合在一起限制两行以内，所以文字要控制在较短长度
        block_text = title + text
        y_analysis = draw_wrapped_block_limited(
            c,
            block_text,
            text_x3,
            y_analysis,
            wrap_width3,
            body_font3,
            body_size3,
            line_height3,
            max_lines=2,
        )
        y_analysis -= line_height3  # 段落之间空一行

    c.showPage()

    # ------------------------------------------------------------------
    # 第 4 页：性格の違いとコミュニケーション
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130          # 左边起点（跟小标题差不多一条线）
    wrap_width = 360      # 行宽稍微拉长一点
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # ===== 話し方とテンポ =====
    y = 625
    body_1 = (
        "太郎 さんは、自分の気持ちを言葉にするまでに少し時間をかける、"
        "じっくりタイプです。一方で、花子 さんは、その場で感じたことをすぐに言葉にする、"
        "テンポの速いタイプです。日常会话では、片方が考えている间にもう一方がどんどん話してしまい、"
        "「ちゃんと聞いてもらえていない」と感觉る场面が出やすくなります。"
    )
    summary_1 = (
        "一言でいうと、二人の話し方は「スピードの違いを理解し合うことで"
        "心地よくつながれるペア」です。"
    )
    y = draw_wrapped_block(c, body_1, text_x, y, wrap_width,
                           body_font, body_size, line_height)
    y -= line_height
    draw_wrapped_block_limited(c, summary_1, text_x, y, wrap_width,
                               body_font, body_size, line_height, 2)

    # ===== 問題への向き合い方 =====
    y2 = 434
    body_2 = (
        "太郎 さんは、問題が起きたときにまず全体を整理してから、落ち着いて対処しようとします。"
        "花子 さんは、感情の動きに敏感で、まず気持ちを共有したいタイプです。"
        "同じ出来事でも、片方は「どう解決するか」、もう片方は「どう感觉たか」を大事にするため、"
        "タイミングがずれると、すれ違いが生まれやすくなります。"
    )
    summary_2 = (
        "一言でいうと、二人は「解決志向」と「共感志向」が支え合う、"
        "心強いバランス型のペアです。"
    )
    y2 = draw_wrapped_block(c, body_2, text_x, y2, wrap_width,
                            body_font, body_size, line_height)
    y2 -= line_height
    draw_wrapped_block_limited(c, summary_2, text_x, y2, wrap_width,
                               body_font, body_size, line_height, 2)

    # ===== 価値観のズレ =====
    y3 = 236
    body_3 = (
        "太郎 さんは、安定や責任感を重视する一方で、花子 さんは、変化やワクワク感を大切にする傾向があります。"
        "お金の使い方や休日の过ごし方、将来のイメージなど、小さな違いが积み重なると、"
        "「なんでわかってくれないの？」と感觉る瞬间が出てくるかもしれません。"
    )
    summary_3 = (
        "一言でいうと、二人の価値観は違いを否定するのではなく、"
        "「お互いの世界を広げ合うきっかけ」になる组合せです。"
    )
    y3 = draw_wrapped_block(c, body_3, text_x, y3, wrap_width,
                            body_font, body_size, line_height)
    y3 -= line_height
    draw_wrapped_block_limited(c, summary_3, text_x, y3, wrap_width,
                               body_font, body_size, line_height, 2)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 5 页：ふたりの強みと課題ポイント
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_points.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # ===== ふたりの「いいところ」 =====
    y = 625
    body_4 = (
        "太郎 さんは、相手の立場を考えながら行動できる、落ち着いた安心感のあるタイプです。"
        "花子 さんは、その場の空気を明るくし、素直な気持ちを伝えられるタイプです。"
        "二人が一緒にいると、「安心感」と「温かさ」が自然と周りにも伝わり、"
        "お互いの长所を引き出し合える関係になりやすい组合せです。"
    )
    summary_4 = (
        "一言でいうと、二人は「一緒にいるだけで場がやわらぎ、"
        "温かさが自然と伝わっていくペア」です。"
    )
    y = draw_wrapped_block(c, body_4, text_x, y, wrap_width,
                           body_font, body_size, line_height)
    y -= line_height
    draw_wrapped_block(c, summary_4, text_x, y, wrap_width,
                       body_font, body_size, line_height)

    # ===== すれ違いやすいポイント =====
    y2 = 434
    body_5 = (
        "太郎 さんは、物事を決めるときに慎重に考えたいタイプで、"
        "花子 さんは、流れや直感を大切にして「とりあえずやってみよう」と思うことが多いかもしれません。"
        "そのため、決断のペースや優先順位がずれると、"
        "「どうしてそんなに急ぐの？」「どうしてそんなに慎重なの？」とお互いに感じやすくなります。"
    )
    summary_5 = (
        "一言でいうと、二人のすれ違いは「慎重さ」と「フットワークの軽さ」の差ですが、"
        "そのギャップは视野を広げるヒントにもなります。"
    )
    y2 = draw_wrapped_block(c, body_5, text_x, y2, wrap_width,
                            body_font, body_size, line_height)
    y2 -= line_height
    draw_wrapped_block(c, summary_5, text_x, y2, wrap_width,
                       body_font, body_size, line_height)

    # ===== 伸ばしていけるポイント =====
    y3 = 236
    body_6 = (
        "太郎 さんの安定感と、花子 さんの柔軟さ・明るさが合わさることで、"
        "二人は「現実的で無理のないチャレンジ」を积み重ねていけるペアです。"
        "お互いの考え方を一度言葉にして共有する習惯ができると、"
        "二人だけのペースや目标が见つかり、将来像もより具体的に描きやすくなります。"
    )
    summary_6 = (
        "一言でいうと、二人の伸ばしていけるポイントは「安心できる土台の上で、"
        "新しい一歩を一緒に踏み出せる力」です。"
    )
    y3 = draw_wrapped_block(c, body_6, text_x, y3, wrap_width,
                            body_font, body_size, line_height)
    y3 -= line_height
    draw_wrapped_block(c, summary_6, text_x, y3, wrap_width,
                       body_font, body_size, line_height)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 6 页：関係の方向性と今後の傾向
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_trend.jpg")
    # 整页文字颜色稍微调浅一点
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # ===== 今の関係ステージ =====
    y = 620
    body_stage = (
        "今の二人の関係は、日常の中に安心感がありつつも、"
        "まだお互いを深く知っていく途中のステージにあります。"
        "気軽さとドキドキ感が同居している時期ともいえます。"
    )
    summary_stage = (
        "一言でいうと、「落ち着きつつも、まだ伸びしろの多い関係」です。"
    )

    y = draw_wrapped_block(c, body_stage, text_x, y,
                           wrap_width, body_font, body_size, line_height)
    y -= line_height
    draw_wrapped_block(c, summary_stage, text_x, y,
                       wrap_width, body_font, body_size, line_height)

    # ===== 発展の流れ（中央の表） =====
    # 整个区块往上移一点：原来 460 → 466
    y2 = 466
    body_flow = (
        "二人の関係は、出会い期・成長期・安定期という流れの中で、"
        "少しずつお互いのペースが見えてくるタイプです。"
    )
    y2 = draw_wrapped_block(c, body_flow, text_x, y2,
                            wrap_width, body_font, body_size, line_height)

    # ★ 说明文字和整张表格之间的间距
    #   数字越大，整张表（段階/特徴+三行+三条线）越往下
    table_top = y2 - line_height * 1.6

    # 表头：段階／特徴
    c.setFont(body_font, body_size)
    header_base = table_top
    c.drawString(text_x, header_base, "段階")
    c.drawString(text_x + 80, header_base, "特徴")

    # 线条颜色 & 粗细（维持你现在的浅灰色）
    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.setLineWidth(0.4)

    # 表头下面的第一条横线
    c.line(text_x, header_base - 4, text_x + wrap_width, header_base - 4)

    # 第 1 行数据 baseline（从表头再往下 1 行）
    y2 = header_base - line_height

    # ===== 三阶段文字（最多 2 行）=====
    rows = [
        ("出会い期",
         "最初はお互いの新鮮さが強く、ドキドキや憧れが中心になります。"
         "第一印象が固まりやすい時期です。"),

        ("成長期",
         "相手の弱さや価値観の違いが見えてきて、摩擦と理解をくり返しながら関係を深めていく時期です。"),

        ("安定期",
         "お互いのペースや居場所がわかってきて、安心感と居心地の良さがベースになる時期です。"),
    ]
    max_lines = 2

    for label, desc in rows:
        row_top = y2

        c.setFont(body_font, body_size)
        c.drawString(text_x, row_top, label)

        draw_wrapped_block_limited(
            c,
            desc,
            text_x + 80,
            row_top,
            wrap_width - 80,
            body_font,
            body_size,
            line_height,
            max_lines,
        )

        y2 = row_top - max_lines * line_height

        c.line(text_x, y2 + 4, text_x + wrap_width, y2 + 4)

        y2 -= line_height

    # ===== バランスを保つコツ =====
    y3 = 170
    body_tip = (
        "二人が長く心地よく付き合っていくためには、"
        "どちらか一方のペースや考えに寄りかかりすぎないことがポイントになります。"
        "ときどき立ち止まって、「今どんな気持ち？」と確認し合うことで、"
        "小さなモヤモヤを大きなすれ違いになる前にケアできます。"
    )

    # 只保留一段
    y3 = draw_wrapped_block(c, body_tip, text_x, y3,
                            wrap_width, body_font, body_size, line_height)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 7 页：日常で役立つアドバイス
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_advice.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    # 表全体的设置
    table_x = 130          # 左边起点（跟前几页保持一致）
    table_width = 360      # 整个表格宽度
    col1_width = 140       # 左列「ふたりのシーン」宽度
    col_gap = 20           # 两列之间的间距
    col2_width = table_width - col1_width - col_gap  # 右列宽度

    body_font = JP_SERIF
    body_size = 11         # 这一页用小一号字体
    line_height = 16

    # 表头位置（下面的内容都以这个为基准往下排）
    header_y = 680         # 整个表稍微往上提一点

    # 表头：用ゴシック体 + 大一号字号，来当「粗体」
    header_font_size = body_size + 2   # 比正文大 2pt，更显眼
    c.setFont(JP_SANS, header_font_size)
    c.drawString(table_x, header_y, "ふたりのシーン")
    c.drawString(table_x + col1_width + col_gap, header_y, "うまくいくコツ")


    # 横线样式（只画横线，不画竖线，风格跟第 6 页一致）
    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.setLineWidth(0.4)

    # 表头下面的第一条横线（比之前再往下一点，别贴着表头）
    c.line(table_x, header_y - 8, table_x + table_width, header_y - 8)

    # 第 1 行内容的起点
    y_row = header_y - line_height * 1.8

    # 每一行： (左列シーン, 右列うまくいくコツ)
    advice_rows = [
        (
            "忙しい平日の夜",
            "10分だけ携帯を置いて、お互いに「今日いちばん嬉しかったこと」を一つずつ話してみましょう。"
        ),
        (
            "休みの日のデート前",
            "予定を決める前に「今日はどんな気分？」と聞くひと言だけで、行き先のすれ違いが減りやすくなります。"
        ),
        (
            "気持ちがすれ違ったとき",
            "どちらが正しいかよりも、「今どう感じた？」を先に聞くと、落ち着いて話し直しやすくなります。"
        ),
        (
            "記念日や特別な日",
            "完璧を目指しすぎず、「お互いに一つずつ感謝を伝える」くらいのシンプルさが、ちょうどいいバランスです。"
        ),
        (
            "相手が疲れていそうな日",
            "アドバイスよりも「今日はおつかれさま」と一言ねぎらうだけで、安心感がぐっと高まります。"
        ),
        (
            "なんとなく距離を感じるとき",
            "重い話ではなく、「最近ハマっていること教えて？」など、軽いテーマから会話をつなげてみましょう。"
        ),
    ]

    # 表身部分用明朝体
    c.setFont(body_font, body_size)

    for scene_text, tip_text in advice_rows:
        # 这一行的顶部基准
        row_top = y_row

        # 左列：ふたりのシーン（不限行数，自动换行）
        scene_y = draw_wrapped_block(
            c,
            scene_text,
            table_x,
            row_top,
            col1_width,
            body_font,
            body_size,
            line_height,
        )

        # 右列：うまくいくコツ（不限行数，自动换行）
        tip_y = draw_wrapped_block(
            c,
            tip_text,
            table_x + col1_width + col_gap,
            row_top,
            col2_width,
            body_font,
            body_size,
            line_height,
        )

        # 这一行实际用到的“最下面的 y”（两列里谁更长就按谁算）
        row_bottom = min(scene_y, tip_y)

        # 该行下方画一条横线（刚好在文字下面一点点）
        c.line(table_x, row_bottom + 4, table_x + table_width, row_bottom + 4)

        # 下一行的起点：在横线下面再空一行
        y_row = row_bottom - line_height

    # ---- 页面下方补一段小总结，让空白不那么明显 ----
    summary_text = (
        "ここに挙げたのはあくまで一例です。"
        "ふたりらしい言葉やタイミングにアレンジしながら、"
        "日常の中で少しずつ「話すきっかけ」を増やしていってください。"
    )
    # 在最后一条横线下方再留一点空隙后开始写
    summary_y_start = y_row - line_height
    draw_wrapped_block(
        c,
        summary_text,
        table_x,
        summary_y_start,
        table_width,
        body_font,
        body_size,
        line_height,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 第 8 页：まとめ（背景のみ + 正文占位）
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_summary.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    # ---- 正文排版参数 ----
    summary_x = 120               # 左右位置
    summary_y = 680               # 你要求的起始位置（往上移）
    summary_wrap_width = 350      # 文本宽度
    summary_font = JP_SERIF
    summary_font_size = 13
    summary_line_height = 20

    # ---- 这里放总结正文（占位内容，之后自动替换为生成文案）----
    summary_text = (
        "【ここに生成された総まとめ文が入ります】"
    )

    # ---- 渲染正文（自动换行）----
    draw_wrapped_block(
        c,
        summary_text,
        summary_x,
        summary_y,
        summary_wrap_width,
        summary_font,
        summary_font_size,
        summary_line_height,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------
    c.save()
    buffer.seek(0)

    filename = f"love_report_{male_name}_{female_name}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# ------------------------------------------------------------------
# Tally webhook（示例）：接收表单 JSON
# ------------------------------------------------------------------
@app.route("/tally_webhook", methods=["POST"])
def tally_webhook():
    """
    Tally 里 Webhook URL 填：
      https://你的域名/tally_webhook

    现在只是把收到的东西打印出来并返回 ok，
    先确认能不能打通，再决定要不要在这里直接生成 PDF / 发邮件。
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    # 线上可以改成写 log 文件，这里先简单 print
    print("Tally webhook payload:", data)
    return {"status": "ok"}


# ------------------------------------------------------------------
# 主程序入口（必须顶格）
# ------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
