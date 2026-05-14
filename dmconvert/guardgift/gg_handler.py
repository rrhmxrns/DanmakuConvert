# Copyright (c) 2025 DanmakuConvert

import json

from .guard_and_gift import (
    merge_gifts,
    adjust_time_conflicts,
    calculate_moves,
    generate_ass_line,
)


def extract_gift_data(element):
    """extract the common attributes of gifts and guards"""
    fixed_time = 2  # the time of gift danmaku
    # B站 XML price 单位系金瓜子，1 CNY = 1000 金瓜子
    raw_price = element.get("price")
    # brec 输出嘅 <gift>/<guard> 顶层冇 price 属性，要从 raw=JSON 入面攞
    if raw_price is None:
        raw_attr = element.get("raw")
        if raw_attr:
            try:
                data = json.loads(raw_attr)
                rp = (
                    data.get("price")
                    or data.get("total_coin")
                    or data.get("discount_price")
                )
                if rp is not None:
                    raw_price = str(rp)
            except (ValueError, TypeError):
                pass
    try:
        price = str(int(raw_price) // 1000)
    except (TypeError, ValueError):
        price = "0"
    data = {
        "appear_time": float(element.get("ts")),
        "over_time": float(element.get("ts")) + fixed_time,
        "user": element.get("user"),
        "name": element.get("giftname"),
        "count": int(element.get("giftcount" if element.tag == "gift" else "count")),
        "price": price,
        "move": 0,
        "height": 0,
        "move_time": -1,
        "disappear_time": -2,
    }
    return data


def draw_gift_and_guard(ass_file, root, sc_font_size, resolution_y):
    with open(ass_file, "a", encoding="utf-8") as f:
        # Convert gifts and guards
        raw_gifts = [
            extract_gift_data(e) for e in root.iter() if e.tag in ("gift", "guard")
        ]

        # data processing pipeline
        processed = merge_gifts(raw_gifts)
        processed = adjust_time_conflicts(processed)
        processed = calculate_moves(processed)

        # generate the output
        for gift in processed:
            lines = generate_ass_line(
                gift, resolution_y, sc_font_size
            )  # example parameters
            f.writelines(lines)
