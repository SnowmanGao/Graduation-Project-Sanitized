import math
from pathlib import Path
from typing import Any

from .paths import DEFAULT_JSON_PATH, DEFAULT_MAP_PATH
from .stream_pipeline import load_json, load_map_json


def as_path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


def import_win32com() -> Any:
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "当前环境缺少 pywin32，无法调用 AutoCAD COM。"
            " 请先安装 pywin32，或改用已安装该依赖的 Python 环境。"
        ) from exc
    return win32com.client


def load_reverse_map(map_path: str | Path) -> dict[str, str]:
    return load_map_json(map_path)


def norm_name(value: Any) -> str:
    return str(value).strip().upper()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_fixed_2(value: float) -> str:
    return f"{float(value):.2f}"


def format_sig_5(value: float) -> str:
    number = float(value)
    if number == 0:
        return "0"
    formatted = f"{number:.5g}"
    if "e" not in formatted and "E" not in formatted and "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def is_block_reference(entity: Any) -> bool:
    try:
        return entity.EntityName == "AcDbBlockReference"
    except Exception:
        return False


def get_effective_block_name(block_ref: Any) -> str:
    try:
        return str(block_ref.EffectiveName)
    except Exception:
        try:
            return str(block_ref.Name)
        except Exception:
            return ""


def get_insertion_point(block_ref: Any) -> tuple[float, float, float] | None:
    try:
        point = tuple(block_ref.InsertionPoint)
        return point[0], point[1], point[2]
    except Exception:
        return None


def has_attributes(block_ref: Any) -> bool:
    try:
        return bool(block_ref.HasAttributes)
    except Exception:
        return False


def get_attributes_dict(block_ref: Any) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    if not has_attributes(block_ref):
        return attributes
    try:
        for attr in block_ref.GetAttributes():
            attributes[norm_name(attr.TagString)] = attr
    except Exception:
        pass
    return attributes


def get_attr_text(block_ref: Any, tag: str) -> str | None:
    attr = get_attributes_dict(block_ref).get(norm_name(tag))
    if attr is None:
        return None
    try:
        return str(attr.TextString).strip()
    except Exception:
        return None


def set_attr_text(block_ref: Any, tag: str, text: str) -> bool:
    attr = get_attributes_dict(block_ref).get(norm_name(tag))
    if attr is None:
        return False
    try:
        attr.TextString = str(text)
        attr.Update()
        return True
    except Exception:
        return False


def collect_block_references(model_space: Any) -> list[Any]:
    return [entity for entity in model_space if is_block_reference(entity)]


def distance_2d(point_a: tuple[float, float, float], point_b: tuple[float, float, float]) -> float:
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


def find_nearby_info_block(
    stream_block: Any, all_blocks: list[Any], radius: float, info_block_names: list[str]
) -> Any | None:
    center = get_insertion_point(stream_block)
    if center is None:
        return None

    info_names = {norm_name(name) for name in info_block_names}
    best_block = None
    best_distance = math.inf

    for block in all_blocks:
        if block is stream_block:
            continue
        if norm_name(get_effective_block_name(block)) not in info_names:
            continue
        point = get_insertion_point(block)
        if point is None:
            continue
        current_distance = distance_2d(center, point)
        if current_distance <= radius and current_distance < best_distance:
            best_block = block
            best_distance = current_distance

    return best_block


def resolve_stream_name_from_block(
    stream_block: Any, code_attr_tag: str, reverse_map: dict[str, str]
) -> tuple[str | None, str | None]:
    code_value = get_attr_text(stream_block, code_attr_tag)
    if not code_value:
        return None, None
    code_value = code_value.strip()
    return code_value, reverse_map.get(code_value)


def build_payload(stream_data: dict[str, dict[str, Any]], stream_name: str) -> dict[str, str] | None:
    row = stream_data.get(stream_name)
    if row is None:
        return None

    temp = safe_float(row.get("温度"))
    pres = safe_float(row.get("压力"))
    flow = safe_float(row.get("质量流量"))
    if temp is None or pres is None or flow is None:
        return None

    return {
        "TEMP": format_fixed_2(temp),
        "PRES": format_fixed_2(pres / 100.0),
        "FLOW": format_sig_5(flow),
    }


def update_info_block(info_block: Any, payload: dict[str, str], attr_tags: dict[str, str]) -> tuple[bool, bool, bool]:
    ok_temp = set_attr_text(info_block, attr_tags["temp"], payload["TEMP"])
    ok_pres = set_attr_text(info_block, attr_tags["pres"], payload["PRES"])
    ok_flow = set_attr_text(info_block, attr_tags["flow"], payload["FLOW"])
    return ok_temp, ok_pres, ok_flow


def apply_to_autocad(
    json_path: str | Path = DEFAULT_JSON_PATH,
    map_path: str | Path = DEFAULT_MAP_PATH,
    stream_code_block_name: str = "流股代号",
    stream_code_attr_tag: str = "0101",
    info_block_names: list[str] | None = None,
    pres_attr_tag: str = "PRES",
    temp_attr_tag: str = "TEMP",
    flow_attr_tag: str = "FLOW",
    search_radius: float = 15.0,
    verbose: bool = True,
) -> dict[str, int]:
    if info_block_names is None:
        info_block_names = ["流股信息表-右", "流股信息表-左", "流股信息表-上", "流股信息表-下"]

    def log(message: str) -> None:
        if verbose:
            print(message)

    json_path = as_path(json_path)
    map_path = as_path(map_path)
    stream_data = load_json(json_path)
    reverse_map = load_reverse_map(map_path)
    win32_client = import_win32com()

    try:
        acad = win32_client.Dispatch("AutoCAD.Application")
        document = acad.ActiveDocument
        model_space = document.ModelSpace
    except Exception as exc:
        raise RuntimeError(
            "无法连接 AutoCAD COM 对象。"
            " 请确认 AutoCAD 已安装、已打开，并且当前会话可以访问 ActiveDocument。"
        ) from exc

    all_blocks = collect_block_references(model_space)
    normalized_code_block_name = norm_name(stream_code_block_name)
    attr_tags = {
        "temp": temp_attr_tag,
        "pres": pres_attr_tag,
        "flow": flow_attr_tag,
    }

    total_stream_blocks = 0
    updated_count = 0
    skipped_count = 0

    for block in all_blocks:
        if norm_name(get_effective_block_name(block)) != normalized_code_block_name:
            continue

        total_stream_blocks += 1
        code_value, stream_name = resolve_stream_name_from_block(block, stream_code_attr_tag, reverse_map)

        if not code_value:
            log("[跳过] 流股代号块缺少目标属性或属性值为空")
            skipped_count += 1
            continue
        if not stream_name:
            log(f"[跳过] map.json 中未找到编号 {code_value!r} 的映射")
            skipped_count += 1
            continue

        payload = build_payload(stream_data, stream_name)
        if payload is None:
            log(f"[跳过] JSON 中未找到流股 {stream_name!r}，或缺少 温度/压力/质量流量")
            skipped_count += 1
            continue

        info_block = find_nearby_info_block(block, all_blocks, search_radius, info_block_names)
        if info_block is None:
            log(f"[跳过] {code_value} -> {stream_name}，附近未找到信息表块")
            skipped_count += 1
            continue

        ok_temp, ok_pres, ok_flow = update_info_block(info_block, payload, attr_tags)
        if ok_temp and ok_pres and ok_flow:
            log(
                f"[完成] {code_value} ({stream_name}) |> "
                f"T={payload['TEMP']} P={payload['PRES']} F={payload['FLOW']}"
            )
            updated_count += 1
        else:
            log(
                f"[部分失败] {code_value} -> {stream_name} |> "
                f"属性写入结果 T={ok_temp}, P={ok_pres}, F={ok_flow}"
            )
            skipped_count += 1

    summary = {
        "total_stream_blocks": total_stream_blocks,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
    }
    print(
        f"处理完成: 流股代号块 {total_stream_blocks} 个, "
        f"成功更新 {updated_count} 个, 跳过/失败 {skipped_count} 个"
    )
    return summary
