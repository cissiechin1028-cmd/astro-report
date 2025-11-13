# ------------------------------------------------------------------
# 第 3 页：基本ホロスコープと総合相性
# 背景：page_basic.jpg
# 星盘：chart_base.png + 行星标注
# ------------------------------------------------------------------
draw_full_bg(c, "page_basic.jpg")

chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
chart_img = ImageReader(chart_path)

# ★ 星盘大小 / 位置（更上方 & 更自然）
chart_size = 165
left_x = 65
left_y = 560
right_x = PAGE_WIDTH - chart_size - 65
right_y = left_y

# 绘制星盘（男左 / 女右）
c.drawImage(chart_img, left_x, left_y,
            width=chart_size, height=chart_size, mask="auto")
c.drawImage(chart_img, right_x, right_y,
            width=chart_size, height=chart_size, mask="auto")

# ★ 行星圆点尺寸（变小、更精致）
dot_r = 4

def draw_dot_text(cx, cy, r, text, color=(0.2, 0.2, 0.8)):
    c.setFillColorRGB(*color)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFillColorRGB(color[0], color[1], color[2])
    c.setFont(font, 10)
    c.drawString(cx + 6, cy - 3, text)

# ==========================================================
# ★ 示例行星位置（你之后可替换成真实占星计算结果）
#   这些位置都刻意避开星座符号，分布在中环区域
# ==========================================================

# 男 星盘（蓝色）
male_planets = [
    (left_x + 78, left_y + 128, "太陽"),
    (left_x + 112, left_y + 144, "月"),
    (left_x + 42, left_y + 110, "火星"),
    (left_x + 130, left_y + 65, "金星"),
    (left_x + 145, left_y + 30, "ASC"),
]

for px, py, label in male_planets:
    draw_dot_text(px, py, dot_r, label, color=(0.18, 0.3, 0.8))

# 女 星盘（粉色）
female_planets = [
    (right_x + 92, right_y + 130, "太陽"),
    (right_x + 122, right_y + 145, "月"),
    (right_x + 45, right_y + 115, "火星"),
    (right_x + 135, right_y + 70, "金星"),
    (right_x + 150, right_y + 35, "ASC"),
]

for px, py, label in female_planets:
    draw_dot_text(px, py, dot_r, label, color=(0.85, 0.2, 0.45))

# ---------------------------------------------
# 姓名（星盘下）
# ---------------------------------------------
c.setFont(font, 14)
c.setFillColorRGB(0, 0, 0)
c.drawCentredString(left_x + chart_size / 2, left_y - 22, f"{male_name} さん")
c.drawCentredString(right_x + chart_size / 2, right_y - 22, f"{female_name} さん")

# ---------------------------------------------
# ★ 两段说明文字（你截图中左下角那两个勾选文字）
# ---------------------------------------------
c.setFont(font, 13)
c.setFillColorRGB(0, 0, 0)

# 勾选符号
check = "☑ "

# 第一行
c.drawString(80, 450, check + "総合相性スコア")

# 第二行
c.drawString(80, 400, check + "太陽・月・上昇の分析")

c.showPage()
