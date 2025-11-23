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
import swisseph as swe


# -------------------------------------------------------------
# 基本目录
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

# -------------------------------------------------------------
# Swiss Ephemeris（使用 Moshier，不需要 ephe 文件）
# -------------------------------------------------------------
def lon_to_sign_name(lon):
    SIGNS_JA = [
        "牡羊座","牡牛座","双子座","蟹座","獅子座","乙女座",
        "天秤座","蠍座","射手座","山羊座","水瓶座","魚座",
    ]
    return SIGNS_JA[int(lon // 30) % 12]


def compute_core_from_birth(dob_str, time_str, place_name):
    try:
        y, m, d = [int(x) for x in dob_str.split("-")]
    except:
        y, m, d = 1990, 1, 1

    try:
        hh, mm = [int(x) for x in time_str.split(":")]
    except:
        hh, mm = 12, 0

    local_hour = hh + mm / 60
    ut_hour = local_hour - 9.0

    lon = 139.6917
    lat = 35.6895

    jd = swe.julday(y, m, d, ut_hour)

    def calc(body):
        lon_val = swe.calc_ut(jd, body, swe.FLG_MOSEPH)[0]
        return lon_val, lon_to_sign_name(lon_val)

    sun_lon, sun_sign = calc(swe.SUN)
    moon_lon, moon_sign = calc(swe.MOON)
    venus_lon, venus_sign = calc(swe.VENUS)
    mars_lon, mars_sign = calc(swe.MARS)

    houses, ascmc = swe.houses(jd, lat, lon)
    asc_lon = ascmc[0]
    asc_sign = lon_to_sign_name(asc_lon)

    return {
        "sun": {"lon": sun_lon, "sign": sun_sign},
        "moon": {"lon": moon_lon, "sign": moon_sign},
        "venus": {"lon": venus_lon, "sign": venus_sign},
        "mars": {"lon": mars_lon, "sign": mars_sign},
        "asc": {"lon": asc_lon, "sign": asc_sign},
    }


# -------------------------------------------------------------
# Flask
# -------------------------------------------------------------
app = Flask(__name__, static_url_path="", static_folder="public")

PAGE_WIDTH, PAGE_HEIGHT = A4

# 字体
JP_SANS = "HeiseiKakuGo-W5"
JP_SERIF = "HeiseiMin-W3"
pdfmetrics.registerFont(UnicodeCIDFont(JP_SANS))
pdfmetrics.registerFont(UnicodeCIDFont(JP_SERIF))


# -------------------------------------------------------------
# 基础绘图工具
# -------------------------------------------------------------
def draw_full_bg(c, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, PAGE_WIDTH, PAGE_HEIGHT)


def get_display_date(raw_date):
    if raw_date:
        try:
            d = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        except:
            d = datetime.date.today()
    else:
        d = datetime.date.today()
    return f"{d.year}年{d.month}月{d.day}日"


def draw_wrapped_block(c, text, x, y, width, font, size, line_h):
    c.setFont(font, size)
    line = ""
    for ch in text:
        if ch == "\n":
            c.drawString(x, y, line)
            y -= line_h
            line = ""
            continue
        if pdfmetrics.stringWidth(line + ch, font, size) <= width:
            line += ch
        else:
            c.drawString(x, y, line)
            y -= line_h
            line = ch
    if line:
        c.drawString(x, y, line)
        y -= line_h
    return y

# ==============================================================
#                  字体注册 & 全局参数
# ==============================================================

from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics

JP_SANS = "HeiseiKakuGo-W5"
JP_SERIF = "HeiseiMin-W3"
pdfmetrics.registerFont(UnicodeCIDFont(JP_SANS))
pdfmetrics.registerFont(UnicodeCIDFont(JP_SERIF))

from reportlab.lib.pagesizes import A4
PAGE_WIDTH, PAGE_HEIGHT = A4


# ==============================================================
#                     公共绘制函数
# ==============================================================

def draw_full_bg(c, filename):
    path = os.path.join("assets", filename)
    try:
        c.drawImage(path, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)
    except:
        pass


def draw_page_number(c, num):
    c.setFont(JP_SANS, 10)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(PAGE_WIDTH / 2, 20, f"{num}")


def draw_wrapped_block(
    c, text, x, y, wrap_width, font_name, font_size, line_height
):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import Frame

    style = ParagraphStyle(
        "jp",
        fontName=font_name,
        fontSize=font_size,
        leading=line_height,
        textColor="black",
        alignment=TA_LEFT,
    )
    paragraph = Paragraph(text.replace("\n", "<br/>"), style)

    f = Frame(
        x, y - 500,
        wrap_width,
        500,
        leftPadding=0,
        bottomPadding=0,
        rightPadding=0,
        topPadding=0,
        showBoundary=0,
    )
    f.addFromList([paragraph], c)
    return y - paragraph.height


def draw_wrapped_block_limited(
    c,
    text,
    x,
    y,
    wrap_width,
    font_name,
    font_size,
    line_height,
    max_lines=1,
):
    """画单行摘要（只取前 max_lines 行）"""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    c.setFont(font_name, font_size)

    words = list(text)
    current = ""
    lines = []

    for ch in words:
        w = stringWidth(current + ch, font_name, font_size)
        if w <= wrap_width:
            current += ch
        else:
            lines.append(current)
            current = ch
            if len(lines) >= max_lines:
                break

    if len(lines) < max_lines and current:
        lines.append(current)

    for line in lines[:max_lines]:
        c.drawString(x, y, line)
        y -= line_height

    return y

# ==============================================================
#           星盘核心计算（Swiss Ephemeris）
# ==============================================================

SIGNS_JA = [
    "牡羊座","牡牛座","双子座","蟹座","獅子座","乙女座",
    "天秤座","蠍座","射手座","山羊座","水瓶座","魚座",
]

def lon_to_sign(lon):
    return SIGNS_JA[int(lon // 30) % 12]


def compute_core_from_birth(dob_str, time_str, place_str):
    """使用 swisseph 计算 Sun / Moon / Venus / Mars / ASC"""
    try:
        y, m, d = [int(x) for x in dob_str.split("-")]
    except:
        y, m, d = 1990, 1, 1

    try:
        hh, mm = [int(x) for x in time_str.split(":")]
    except:
        hh, mm = 12, 0

    local_hour = hh + mm / 60
    ut_hour = local_hour - 9  # 日本 → UT

    jd = swe.julday(y, m, d, ut_hour)

    sun_lon   = swe.calc_ut(jd, swe.SUN)[0]
    moon_lon  = swe.calc_ut(jd, swe.MOON)[0]
    venus_lon = swe.calc_ut(jd, swe.VENUS)[0]
    mars_lon  = swe.calc_ut(jd, swe.MARS)[0]

    lat = 35.6895
    lon = 139.6917
    houses, ascmc = swe.houses(jd, lat, lon)

    asc_lon = ascmc[0]

    return {
        "sun":   {"lon": sun_lon,   "sign_jp": lon_to_sign(sun_lon)},
        "moon":  {"lon": moon_lon,  "sign_jp": lon_to_sign(moon_lon)},
        "venus": {"lon": venus_lon, "sign_jp": lon_to_sign(venus_lon)},
        "mars":  {"lon": mars_lon,  "sign_jp": lon_to_sign(mars_lon)},
        "asc":   {"lon": asc_lon,   "sign_jp": lon_to_sign(asc_lon)},
    }


# ==============================================================
#             Page3：基本星盘 + 总体相性说明
# ==============================================================

def build_pair_overall_text(your_core, partner_core):
    """
    返回 Page3 用的 “相性说明文本”（不再使用评分）
    """
    your_sun = your_core["sun"]["sign_jp"]
    partner_sun = partner_core["sun"]["sign_jp"]

    # 12星座 → 元素
    SIGN_ELEMENT = {
        "牡羊座":"fire","獅子座":"fire","射手座":"fire",
        "牡牛座":"earth","乙女座":"earth","山羊座":"earth",
        "双子座":"air","天秤座":"air","水瓶座":"air",
        "蟹座":"water","蠍座":"water","魚座":"water",
    }

    e1 = SIGN_ELEMENT.get(your_sun, "")
    e2 = SIGN_ELEMENT.get(partner_sun, "")

    PAIR_TEXT = {
        ("fire","fire"): "情熱が共鳴し、自然と距離が縮まりやすいペアです。",
        ("fire","earth"): "勢いと安定が調和し、支え合いながら前進できる関係です。",
        ("fire","water"): "情熱と感受性が響き合う、心の動きが大きいペアです。",
        ("air","fire"): "発想と行動力が噛み合い、刺激が多い組み合わせです。",
        ("earth","earth"): "価値観が似やすく、安心できる落ち着いた相性です。",
        ("air","air"): "会話や感性が似ており、一緒にいて気楽な関係です。",
        ("water","water"): "深い共感が生まれやすく、支え合える優しい相性です。",
    }

    txt = PAIR_TEXT.get((e1, e2)) or PAIR_TEXT.get((e2, e1)) or \
        "お互いの違いを補い合いながら、自然と成長していける組み合わせです。"

    return (
        f"太陽星座を見ると、あなた（{your_sun}）とお相手（{partner_sun}）は、"
        f"{txt}"
        "違いがあっても、その違いが新しい視点をもたらし、関係を深めるきっかけになります。"
    )


def draw_page3_basic_and_synastry(
    c,
    your_name,
    partner_name,
    your_core,
    partner_core,
    summary_text
):
    draw_full_bg(c, "page_basic.jpg")
    c.setFillColorRGB(0.2,0.2,0.2)

    # 星座文字，左=你的，右=对方
    c.setFont(JP_SANS, 14)

    def draw_one(label, core, x, y):
        c.drawString(x, y, f"{label}：{core['sign_jp']}")

    draw_one("太陽", your_core["sun"], 120, 610)
    draw_one("月",   your_core["moon"], 120, 580)
    draw_one("金星", your_core["venus"], 120, 550)
    draw_one("火星", your_core["mars"], 120, 520)
    draw_one("ASC",  your_core["asc"], 120, 490)

    draw_one("太陽", partner_core["sun"], 330, 610)
    draw_one("月",   partner_core["moon"], 330, 580)
    draw_one("金星", partner_core["venus"], 330, 550)
    draw_one("火星", partner_core["mars"], 330, 520)
    draw_one("ASC",  partner_core["asc"], 330, 490)

    # 总体相性说明
    draw_wrapped_block(
        c,
        summary_text,
        120,
        430,
        350,
        JP_SERIF,
        13,
        20,
    )

    draw_page_number(c, 3)
    c.showPage()

# ==============================================================
#           第 4〜7 页：页面绘制函数（已全部保留）
# ==============================================================

def draw_page4_communication(
    c,
    talk_text, talk_summary,
    problem_text, problem_summary,
    values_text, values_summary,
):
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    font = JP_SERIF
    size = 12
    lh = 18

    y = draw_wrapped_block(c, talk_text, text_x, 625, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, talk_summary, text_x, y, wrap_width, font, size, lh, 1)

    y = draw_wrapped_block(c, problem_text, text_x, 434, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, problem_summary, text_x, y, wrap_width, font, size, lh, 1)

    y = draw_wrapped_block(c, values_text, text_x, 236, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, values_summary, text_x, y, wrap_width, font, size, lh, 1)

    draw_page_number(c, 4)
    c.showPage()


def draw_page5_points(
    c,
    good_text, good_summary,
    gap_text, gap_summary,
    hint_text, hint_summary,
):
    draw_full_bg(c, "page_points.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    font = JP_SERIF
    size = 12
    lh = 18

    y = draw_wrapped_block(c, good_text, text_x, 625, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, good_summary, text_x, y, wrap_width, font, size, lh, 1)

    y = draw_wrapped_block(c, gap_text, text_x, 434, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, gap_summary, text_x, y, wrap_width, font, size, lh, 1)

    y = draw_wrapped_block(c, hint_text, text_x, 236, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, hint_summary, text_x, y, wrap_width, font, size, lh, 1)

    draw_page_number(c, 5)
    c.showPage()


def draw_page6_trend(
    c,
    theme_text, theme_summary,
    emotion_text, emotion_summary,
    style_text, style_summary,
    future_text, future_summary,
):
    draw_full_bg(c, "page_trend.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    font = JP_SERIF
    size = 12
    lh = 18

    y = draw_wrapped_block(c, theme_text, text_x, 620, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, theme_summary, text_x, y, wrap_width, font, size, lh, 1)

    y = draw_wrapped_block(c, emotion_text, text_x, 460, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, emotion_summary, text_x, y, wrap_width, font, size, lh, 1)

    y = draw_wrapped_block(c, style_text, text_x, 300, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, style_summary, text_x, y, wrap_width, font, size, lh, 1)

    y = draw_wrapped_block(c, future_text, text_x, 145, wrap_width, font, size, lh)
    y -= lh
    draw_wrapped_block_limited(c, future_summary, text_x, y, wrap_width, font, size, lh, 1)

    draw_page_number(c, 6)
    c.showPage()


def draw_page7_advice(c, advice_rows, footer_text):
    draw_full_bg(c, "page_advice.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    x = 130
    width = 360
    col1 = 140
    col_gap = 20
    col2 = width - col1 - col_gap

    font = JP_SERIF
    size = 11
    lh = 16

    header_y = 680
    c.setFont(JP_SANS, size + 2)
    c.drawString(x, header_y, "ふたりのシーン")
    c.drawString(x + col1 + col_gap, header_y, "うまくいくコツ")

    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.line(x, header_y - 8, x + width, header_y - 8)

    y = header_y - lh * 1.8
    c.setFont(font, size)

    for scene, tip in advice_rows:
        scene_y = draw_wrapped_block(c, scene, x, y, col1, font, size, lh)
        tip_y = draw_wrapped_block(c, tip, x + col1 + col_gap, y, col2, font, size, lh)
        row_bottom = min(scene_y, tip_y)
        c.line(x, row_bottom + 4, x + width, row_bottom + 4)
        y = row_bottom - lh

    draw_wrapped_block(c, footer_text, x, y - lh, width, font, size, lh)
    draw_page_number(c, 7)
    c.showPage()


# ==============================================================
#                       Page 8：まとめ
# ==============================================================

def build_page8_summary(your_name, partner_name):
    return (
        f"{your_name} さんと {partner_name} さんの関係は、"
        "安心感と自然な前進力を持つ、とてもバランスの良いペアです。\n\n"
        "日々の小さな言葉や気遣いが、ふたりの未来をより豊かにしていきます。"
    )


# ==============================================================
#                     生成 PDF 主处理逻辑
# ==============================================================

@app.route("/api/generate_report", methods=["GET", "POST"])
def generate_report():
    your_name = request.args.get("your_name") or ""
    partner_name = request.args.get("partner_name") or ""

    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    your_dob = request.args.get("your_dob") or "1990-01-01"
    your_time = request.args.get("your_time") or "12:00"
    your_place = request.args.get("your_place") or "Tokyo"

    partner_dob = request.args.get("partner_dob") or "1990-01-01"
    partner_time = request.args.get("partner_time") or "12:00"
    partner_place = request.args.get("partner_place") or "Tokyo"

    your_core = compute_core_from_birth(your_dob, your_time, your_place)
    partner_core = compute_core_from_birth(partner_dob, partner_time, partner_place)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # cover
    draw_full_bg(c, "cover.jpg")
    c.setFont(JP_SANS, 20)
    c.drawCentredString(PAGE_WIDTH/2, 420, f"{your_name} さん ＆ {partner_name} さん")
    c.setFont(JP_SANS, 12)
    c.drawCentredString(PAGE_WIDTH/2, 80, f"作成日：{date_display}")
    c.showPage()

    # index
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # page3
    overall_text = build_pair_overall_text(your_core, partner_core)
    draw_page3_basic_and_synastry(
        c,
        your_name,
        partner_name,
        your_core,
        partner_core,
        overall_text
    )

    # PAGE 4
    talk_text = (
        f"{your_name} さんは、じっくり考えてから言葉にするタイプ。"
        f"{partner_name} さんは、感じたことをすぐ伝えるタイプです。"
        "この話す速度の違いが誤解を生む場面があります。"
    )
    talk_summary = "話すスピードの違いを理解し合うことで心地よくつながれます。"

    problem_text = (
        f"{your_name} さんは冷静に整理し、{partner_name} さんは感情を共有したいタイプ。"
        "解決と共感のズレがすれ違いを生みます。"
    )
    problem_summary = "解決志向 × 共感志向が支え合うバランス型です。"

    values_text = (
        f"{your_name} さんは安定、{partner_name} さんは変化を求める傾向があります。"
        "価値観の小さな差が積み重なると誤解が生まれやすくなります。"
    )
    values_summary = "価値観の違いが世界を広げ合うきっかけになります。"

    draw_page4_communication(
        c,
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    )

    # PAGE 5
    good_text = (
        f"{your_name} さんは落ち着いた安心感、"
        f"{partner_name} さんは明るさと素直さを持つタイプです。"
        "二人は互いの長所を自然に引き出します。"
    )
    good_summary = "場をやわらげ、温かさを共有できるペアです。"

    gap_text = (
        f"{your_name} さんは慎重、{partner_name} さんは直感型。"
        "決断のペースの違いが気になることがあります。"
    )
    gap_summary = "慎重さ × フットワークの軽さが視野を広げるヒントに。"

    hint_text = (
        f"{your_name} さんの安定感と、{partner_name} さんの柔軟さは相性抜群。"
        "言葉で共有する習慣が未来像を整えていきます。"
    )
    hint_summary = "安心できる土台の上で新しい一歩を踏み出せます。"

    draw_page5_points(
        c,
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    )

    # PAGE 6
    theme_text = "二人の関係は「安心感」と「前進力」を両立しやすいタイプです。"
    theme_summary = "同じ方向を見て進める安定したテーマです。"

    emotion_text = "感情はゆっくり深まり、一度安心できると自然と距離が縮まります。"
    emotion_summary = "ゆっくり始まり深くつながる流れです。"

    style_text = "自然と役割分担が生まれ、生活や会話のリズムが合いやすい組み合わせです。"
    style_summary = "調和しながら形を作る関係です。"

    future_text = "今後1〜2年は安定の中で小さな前進を重ねる時期です。"
    future_summary = "小さな前進が続くタイミングです。"

    draw_page6_trend(
        c,
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    )

    # PAGE 7
    advice_rows = [
        ("忙しい平日の夜", "10分だけ携帯を置き、互いの嬉しかったことを共有。"),
        ("休みの日のデート前", "予定を決める前に「今日はどんな気分？」と聞く。"),
        ("気持ちがすれ違ったとき", "正しさより「どう感じた？」を優先する。"),
        ("記念日や特別な日", "完璧を求めず、一言の感謝を伝えるだけで十分。"),
        ("相手が疲れていそうな日", "アドバイスより「おつかれさま」の一言を。"),
        ("距離を感じるとき", "軽いテーマから会話をつなげていく。"),
    ]
    footer_text = "ふたりらしい言葉にアレンジしながら、会話のきっかけを増やしてください。"

    draw_page7_advice(c, advice_rows, footer_text)

    # PAGE 8
    summary_text = build_page8_summary(your_name, partner_name)

    draw_full_bg(c, "page_summary.jpg")
    draw_wrapped_block(
        c,
        summary_text,
        120,
        680,
        350,
        JP_SERIF,
        13,
        20,
    )
    c.showPage()

    # finish
    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"love_report_{your_name}_{partner_name}.pdf",
        mimetype="application/pdf",
    )


# ==============================================================
# Tally Webhook（保持原样）
# ==============================================================

@app.route("/tally_webhook", methods=["POST"])
def tally_webhook():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    print("Tally webhook payload:", data)
    return {"status": "ok"}


# ==============================================================
# Server Start
# ==============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
