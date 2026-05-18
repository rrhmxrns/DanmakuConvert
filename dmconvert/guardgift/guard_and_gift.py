# Copyright (c) 2025 DanmakuConvert

from ..utils import format_time, get_color, get_str_len


def merge_gifts(giftlist, merge_interval=5):
    """merge the same user, same gift and the time interval is less than 5 seconds"""
    if not giftlist:
        return []

    # sort by the appear time
    giftlist.sort(key=lambda x: (x["appear_time"]))

    merged = []
    current = giftlist[0].copy()

    for gift in giftlist[1:]:
        if (
            gift["user"] == current["user"]
            and gift["name"] == current["name"]
            and gift["appear_time"] - current["appear_time"] < merge_interval
        ):
            current["count"] += gift["count"]
            current["over_time"] = gift["over_time"]  # keep the last time
        else:
            merged.append(current)
            current = gift.copy()
    merged.append(current)
    return merged


def adjust_time_conflicts(gifts, max_overlap=3, interval=0.4):
    """
        handle the gift danmaku with the same time, avoid overlapping by interval
        s.t. (max_overlap-1)*interval < 1

    Args:
        max_overlap: the max number of the same time gift danmaku
        interval: the interval time
    """
    processed = []
    last_time = -float("inf")
    overlap_count = 0

    for gift in sorted(gifts, key=lambda x: x["appear_time"]):
        if gift["appear_time"] == last_time:
            overlap_count += 1
            if overlap_count >= max_overlap:
                continue  # discard the gift danmaku with more than 5 conflicts
            delta = interval * overlap_count
        else:
            overlap_count = 0
            delta = 0

        adjusted = gift.copy()
        adjusted["appear_time"] += delta
        adjusted["over_time"] += delta
        processed.append(adjusted)
        last_time = gift["appear_time"]  # keep the original time for comparison

    return processed


def calculate_moves(gifts):
    """calculate the time and position of each gift"""
    # generate the event stream
    events = []
    for idx, gift in enumerate(gifts):
        events.append((gift["appear_time"], "start", idx))
        events.append((gift["over_time"], "end", idx))
    events.sort(
        key=lambda x: (x[0], x[1] == "start")
    )  # ensure the end event is processed first

    # status tracking
    active = []
    max_layers = 2

    for time, event_type, idx in events:
        if event_type == "start":
            # trigger the move of the existing active item
            for active_idx in active:
                gift = gifts[active_idx]
                # cap at max_layers: once the gift has been pushed off-screen
                # (move == max_layers) further new arrivals must not bump it
                # again, otherwise generate_ass_line falls through all branches
                # and returns None
                if gift["move"] >= max_layers:
                    continue
                gift["move"] += 1
                gift["height"] += 1

                # record the key time points
                if gift["move"] == 1:
                    gift["move_time"] = time
                elif gift["move"] == 2:
                    gift["disappear_time"] = time

            # add the new active item
            active.append(idx)
            if len(active) > max_layers:
                # remove the earliest one
                expired = active.pop(0)

        else:  # end event
            if idx in active:
                active.remove(idx)

    return gifts


def print_gift_2_ass(
    actionStr, start_time, end_time, height_num, gift_str, resolution_y, font_size,
    box_color="\\c&HB2602A", box_width=300,
):
    # gift danmakus print to ass — 双行输出：圆角半透明底 + 文字
    text_layer = 1
    bg_layer = 0
    pos_x = 0  # left side
    pad_x = int(font_size * 0.4)
    pad_y_top = int(font_size * 0.2)
    pad_y_bot = int(font_size * 0.2)
    radius = max(int(font_size * 0.3), 4)
    box_W = int(box_width + pad_x * 2)
    box_H = int(font_size + pad_y_top + pad_y_bot)

    height = resolution_y - height_num * font_size  # 文字 y
    box_x = pos_x
    box_y = height - pad_y_top
    text_x = pos_x + pad_x

    # 文字 effect（维持原有 move / pos 行为，只系 x 加 pad_x）
    if actionStr == "disappear":
        text_effect = f"\\move({text_x},{height+font_size},{text_x},{height})\\clip(0,{resolution_y-font_size*2},700,{resolution_y},)"
        box_effect = f"\\move({box_x},{box_y+font_size},{box_x},{box_y})\\clip(0,{resolution_y-font_size*2},700,{resolution_y},)"
    elif actionStr == "move":
        text_effect = f"\\move({text_x},{height+font_size},{text_x},{height})"
        box_effect = f"\\move({box_x},{box_y+font_size},{box_x},{box_y})"
    elif actionStr == "pos":
        text_effect = f"\\pos({text_x},{height})"
        box_effect = f"\\pos({box_x},{box_y})"

    # 圆角矩形用 bezier 画（仿 SuperChat 嘅 draw_lower_box pattern）
    box_draw = (
        f"m 0 {radius} "
        f"b 0 {radius//2} {radius//2} 0 {radius} 0 "                               # 左上角
        f"l {box_W - radius} 0 "                                                    # 顶边
        f"b {box_W - radius//2} 0 {box_W} {radius//2} {box_W} {radius} "            # 右上角
        f"l {box_W} {box_H - radius} "                                              # 右边
        f"b {box_W} {box_H - radius//2} {box_W - radius//2} {box_H} {box_W - radius} {box_H} "  # 右下角
        f"l {radius} {box_H} "                                                      # 底边
        f"b {radius//2} {box_H} 0 {box_H - radius//2} 0 {box_H - radius}"           # 左下角
    )

    box_line = f"Dialogue: {bg_layer},{start_time},{end_time},gift_bg,,0000,0000,0000,,{{{box_effect}\\p1{box_color}\\alpha&H60&\\bord0\\shad0}}{box_draw}\n"
    text_line = f"Dialogue: {text_layer},{start_time},{end_time},gift_txt,,0000,0000,0000,,{{{text_effect}}}{gift_str}\n"
    return box_line + text_line


def generate_ass_line(gift, resolution_y, font_size):
    """generate a single ASS line"""
    # The animation time should be kept, not greater than the previous merge_interval of the same start time
    animation_time = 0.2  # the time of gift danmaku moving

    appear_time = gift["appear_time"]
    over_time = gift["over_time"]
    move_time = gift["move_time"]
    disappear_time = gift["disappear_time"]

    start_time = format_time(appear_time)
    end_time = format_time(over_time)
    mid_time = format_time(move_time)
    dis_time = format_time(disappear_time)

    upper_box_color, lower_box_color, user_name_color = get_color(int(gift["price"]))
    # 文字统一白色（box 已经按价格变色，文字用白色确保对比度）
    gift_str = f"{{\\c&HFFFFFF\\b1}}{gift['user']}:{{\\c&HFFFFFF\\b0}} {gift['name']} x{gift['count']}"
    # giftname = f"{gift['name']} x{gift['count']}"

    # 算 box 宽度 — 只凭文字长度，冇 ASS tag 入面
    raw_text = f"{gift['user']}: {gift['name']} x{gift['count']}"
    box_width = int(get_str_len(raw_text, font_size))

    start_time_next = format_time(appear_time + animation_time)
    end_time_next = format_time(over_time + animation_time)
    mid_time_next = format_time(move_time + animation_time)
    dis_time_next = format_time(disappear_time + animation_time)

    move_status = gift["move"]  # the number of moves

    # one move, the upper one disappears earlier
    if move_status == 2:
        line0 = print_gift_2_ass(
            "move", start_time, start_time_next, 1, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line1 = print_gift_2_ass(
            "pos", start_time_next, mid_time, 1, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line2 = print_gift_2_ass(
            "move", mid_time, mid_time_next, 2, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line3 = print_gift_2_ass(
            "pos", mid_time_next, dis_time, 2, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line4 = print_gift_2_ass(
            "disappear", dis_time, dis_time_next, 3, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        return line0 + line1 + line2 + line3 + line4
    # one move, the upper one does not disappear earlier
    elif move_status == 1:
        line0 = print_gift_2_ass(
            "move", start_time, start_time_next, 1, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line1 = print_gift_2_ass(
            "pos", start_time_next, mid_time, 1, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line2 = print_gift_2_ass(
            "move", mid_time, mid_time_next, 2, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line3 = print_gift_2_ass(
            "pos", mid_time_next, end_time, 2, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        return line0 + line1 + line2 + line3
    # one move
    elif move_status == 0:
        line0 = print_gift_2_ass(
            "move", start_time, start_time_next, 1, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        line1 = print_gift_2_ass(
            "pos", start_time_next, end_time, 1, gift_str, resolution_y, font_size,
            box_color=lower_box_color, box_width=box_width,
        )
        return line0 + line1
    # move_status >= 3：被 3+ 个新 gift 推出屏幕，唔再渲染（避免返 None 炸 writelines）
    else:
        return ""
