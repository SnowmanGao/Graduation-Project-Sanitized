# -*- coding: utf-8 -*-
"""
pid_auto_numberer_simple.py

精简版 AutoCAD P&ID 自动仪表编号器。

特点：
1. 只通过 ROT 中的 DWG 文件 Moniker 连接已经打开的目标图纸。
   不再使用 Dispatch("AutoCAD.Application") / GetActiveObject / EnsureDispatch。
2. 只扫描目标文档的 ModelSpace。
3. 只保留 segment_op 编号方式：
   同一工段、同一 OP 独立流水号。
   例如：
       FIC: 0101, 0102
       LI : 0101, 0102
4. 不再保留 OP_ORDER。
   不做 OP 前缀归并。
   因此 LI、LICA、LIA 是不同 OP 组。
5. 每个 OP 组内：
   先取最左上的仪表，再逐个寻找最近的同 OP 仪表编号。

运行：
    python pid_auto_numberer_simple.py --dry-run
    python pid_auto_numberer_simple.py
    python pid_auto_numberer_simple.py --save

如果关键词匹配不到目标 DWG：
    python pid_auto_numberer_simple.py --needle "P&ID"
    python pid_auto_numberer_simple.py --path "E:\\GraduationProject\\图纸\\管道及仪表流程图（P&ID）\\管道及仪表流程图（P&ID）.dwg"

依赖：
    pip install pywin32
"""

from __future__ import annotations

from tqdm import tqdm
import argparse
import math
import os
from dataclasses import dataclass
from typing import Any, Iterable

# =========================
# 用户配置区
# =========================

# 默认按 ROT 中 DWG 路径或显示名的关键词匹配目标图纸。
TARGET_DWG_KEYWORD = "管道及仪表"

# 如需精确指定 DWG 路径，可以填完整路径；留空则使用 TARGET_DWG_KEYWORD。
TARGET_DWG_PATH = ""

# Y 坐标工段切分。
# 例如 1: (-60, -740) 表示 -60 ~ -740 的区域是第 1 工段，编号前缀为 01。
SEGMENTS: dict[int, tuple[float, float]] = {
    1: (-60, -740),
    2: (-750, -1460),
}

# 块定义。
# name    : AutoCAD 块名。
# id_attr : 写入 0101 这类编号的属性标签。
# op_attr : 读取 FIC、LI、PI、LICA 这类操作代号的属性标签。
BLOCK_CONFIG: list[dict[str, str]] = [
    {
        "name": "仪表",
        "id_attr": "0101",
        "op_attr": "PI",
    },
    {
        "name": "仪表2",
        "id_attr": "0101",
        "op_attr": "LICA",
    },
]

# 编号格式：工段号两位 + 流水号两位，即 0101、0102、0201。
SEGMENT_DIGITS = 2
SERIAL_DIGITS = 2


# =========================
# pywin32 / ROT 连接
# =========================


def import_pywin32() -> tuple[Any, Any]:
    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "当前 Python 环境缺少 pywin32，请先执行：pip install pywin32"
        ) from exc
    return pythoncom, win32com.client


def norm_path(value: str) -> str:
    return os.path.normcase(
        os.path.normpath(os.path.abspath(os.path.expanduser(value)))
    )


def safe_str(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return ""


def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def wrap_dispatch(obj: Any) -> Any:
    """把 ROT 返回的 IDispatch 包装成 pywin32 Dispatch 对象。"""
    _pythoncom, win32_client = import_pywin32()
    if hasattr(obj, "_oleobj_"):
        return obj
    return win32_client.Dispatch(obj)


def connect_document_from_rot(
    needle: str = TARGET_DWG_KEYWORD,
    path: str = TARGET_DWG_PATH,
    verbose: bool = True,
) -> tuple[Any, Any, str]:
    """
    只通过 ROT 文件 Moniker 连接已打开的目标 DWG。
    成功返回：(acad_application, acad_document, display_name)

    注意：
    - 这里故意不做 Dispatch/GetActiveObject 兜底，避免误连到隐藏 Drawing1.dwg。
    - 这里故意只使用 moniker.BindToObject(IID_IDispatch)，与你已验证成功的方法一致。
    """
    pythoncom, _win32_client = import_pywin32()
    target_path = norm_path(path) if path else ""

    rot = pythoncom.GetRunningObjectTable()
    enum = rot.EnumRunning()
    bind_ctx = pythoncom.CreateBindCtx(0)

    candidates: list[tuple[str, Any]] = []

    while True:
        monikers = enum.Next(1)
        if not monikers:
            break

        moniker = monikers[0]
        try:
            display_name = safe_str(moniker.GetDisplayName(bind_ctx, None))
        except Exception:
            continue

        if ".dwg" not in display_name.lower():
            continue

        if target_path:
            try:
                display_path = norm_path(display_name)
            except Exception:
                display_path = display_name
            if display_path == target_path:
                candidates.insert(0, (display_name, moniker))
            elif os.path.basename(target_path).lower() in display_name.lower():
                candidates.append((display_name, moniker))
        else:
            if needle.lower() in display_name.lower():
                candidates.append((display_name, moniker))

    if not candidates:
        raise RuntimeError(
            "ROT 中未找到目标 DWG。\n"
            f"needle={needle!r} path={path!r}\n"
            "请确认目标图纸已经在 AutoCAD 中打开，并且文件名或路径包含该关键词。\n"
            f"提示：可以尝试重新启动 AutoCAD 再运行程序！"
        )

    errors: list[str] = []
    for display_name, moniker in candidates:
        try:
            obj = moniker.BindToObject(bind_ctx, None, pythoncom.IID_IDispatch)
            document = wrap_dispatch(obj)
            if safe_get(document, "ModelSpace", None) is None:
                errors.append(f"{display_name}: 绑定成功，但对象没有 ModelSpace")
                continue

            application = safe_get(document, "Application", None)
            if verbose:
                print(f"[连接成功] method=moniker.BindToObject(IID_IDispatch)")
                print(f"  ROT={display_name!r}")
                print(f"  Name={safe_str(safe_get(document, 'Name', ''))!r}")
                full_name = safe_str(safe_get(document, "FullName", ""))
                # if full_name:
                #     print(f"  FullName={full_name!r}")
                print(
                    f"  ModelSpace.Count={safe_get(document.ModelSpace, 'Count', None)!r}"
                )
                if application is not None:
                    print(
                        f"  Application.Caption={safe_str(safe_get(application, 'Caption', ''))!r}"
                    )
            return application, document, display_name
        except Exception as exc:
            errors.append(f"{display_name}: {type(exc).__name__}: {exc}")

    raise RuntimeError("找到了候选 DWG，但绑定失败：\n" + "\n".join(errors))


# =========================
# AutoCAD 块 / 属性工具
# =========================


def norm_text(value: Any) -> str:
    return str(value).strip().upper()


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
        return float(point[0]), float(point[1]), float(point[2])
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
            attributes[norm_text(attr.TagString)] = attr
    except Exception:
        pass
    return attributes


def get_attr_text(block_ref: Any, tag: str) -> str | None:
    attr = get_attributes_dict(block_ref).get(norm_text(tag))
    if attr is None:
        return None
    try:
        return str(attr.TextString).strip()
    except Exception:
        return None


def set_attr_text(block_ref: Any, tag: str, text: str) -> bool:
    attr = get_attributes_dict(block_ref).get(norm_text(tag))
    if attr is None:
        return False
    try:
        attr.TextString = str(text)
        attr.Update()
        return True
    except Exception:
        return False


def iter_com_collection(
    collection: Any,
    desc: str = "",
    unit: str = "个",
    show_progress: bool = False,
) -> Iterable[Any]:
    """
    稳定遍历 AutoCAD COM Collection。
    加入 tqdm 进度条。
    """
    try:
        count = int(collection.Count)
    except Exception:
        return

    iterator = range(count)
    if show_progress:
        iterator = tqdm(
            iterator,
            total=count,
            desc=desc,
            unit=unit,
            ncols=100,
            dynamic_ncols=True,
        )

    for index in iterator:
        try:
            yield collection.Item(index)
        except Exception:
            continue


def collect_block_references_from_model_space(
    document: Any, verbose: bool = True
) -> list[Any]:
    model_space = document.ModelSpace
    blocks: list[Any] = []
    entity_types: dict[str, int] = {}
    entity_count = 0

    for entity in iter_com_collection(
        model_space,
        desc="扫描 ModelSpace",
        unit="实体",
        show_progress=verbose,
    ):
        entity_count += 1
        try:
            entity_name = str(entity.EntityName)
        except Exception:
            entity_name = "<unknown>"
        entity_types[entity_name] = entity_types.get(entity_name, 0) + 1

        if is_block_reference(entity):
            # 注意：这里太坑了一定要从数据库请求才有信息！
            obj = entity.Database.ObjectIdToObject(entity.ObjectID)
            blocks.append(obj)

    if verbose:
        # type_text = ", ".join(f"{k}={v}" for k, v in sorted(entity_types.items())) or "无实体"
        print(f"[扫描 ModelSpace] 实体 {entity_count} 个；" f"块参照 {len(blocks)} 个\n")

    return blocks


# =========================
# 数据模型
# =========================


@dataclass(frozen=True)
class BlockConfig:
    name: str
    id_attr: str
    op_attr: str

    @property
    def normalized_name(self) -> str:
        return norm_text(self.name)


@dataclass
class Instrument:
    pos_x: float
    pos_y: float
    type: str
    op: str
    segment: int
    block: Any
    id_attr: str

    def get_id(self) -> str | None:
        return get_attr_text(self.block, self.id_attr)

    def set_id(self, value: str) -> bool:
        return set_attr_text(self.block, self.id_attr, value)


# =========================
# 扫描与编号逻辑
# =========================


def build_config_map(raw_config: list[dict[str, str]]) -> dict[str, BlockConfig]:
    config_map: dict[str, BlockConfig] = {}
    for row in raw_config:
        config = BlockConfig(
            name=row["name"],
            id_attr=row["id_attr"],
            op_attr=row["op_attr"],
        )
        key = config.normalized_name
        if key in config_map:
            raise ValueError(f"BLOCK_CONFIG 中存在重复块名：{config.name!r}")
        config_map[key] = config
    return config_map


def locate_segment(y: float, segments: dict[int, tuple[float, float]]) -> int | None:
    for segment, (y_a, y_b) in sorted(segments.items()):
        y_min = min(y_a, y_b)
        y_max = max(y_a, y_b)
        if y_min <= y <= y_max:
            return segment
    return None


def collect_instruments(
    all_blocks: Iterable[Any],
    config_map: dict[str, BlockConfig],
    segments: dict[int, tuple[float, float]],
    verbose: bool = True,
) -> tuple[list[Instrument], dict[str, int]]:
    instruments: list[Instrument] = []
    stats = {
        "block_refs": 0,
        "matched_blocks": 0,
        "skipped_no_point": 0,
        "skipped_no_segment": 0,
        "skipped_no_op": 0,
    }

    for block in tqdm(
        list(all_blocks),
        desc="提取 P&ID 仪表块",
        unit="块",
        ncols=100,
        dynamic_ncols=True,
        disable=not verbose,
    ):
        stats["block_refs"] += 1

        block_name = get_effective_block_name(block)
        config = config_map.get(norm_text(block_name))
        if config is None:
            continue

        stats["matched_blocks"] += 1

        point = get_insertion_point(block)
        if point is None:
            stats["skipped_no_point"] += 1
            continue

        pos_x, pos_y, _ = point
        segment = locate_segment(pos_y, segments)
        if segment is None:
            stats["skipped_no_segment"] += 1
            if verbose:
                print(
                    f"[跳过] {block_name} @ ({pos_x:.2f}, {pos_y:.2f}) 不在任何工段范围内"
                )
            continue

        op = get_attr_text(block, config.op_attr)
        if not op:
            stats["skipped_no_op"] += 1
            if verbose:
                print(
                    f"[跳过] {block_name} @ ({pos_x:.2f}, {pos_y:.2f}) "
                    f"属性 {config.op_attr!r} 为空或不存在"
                )
            continue

        instruments.append(
            Instrument(
                pos_x=pos_x,
                pos_y=pos_y,
                type=block_name,
                op=op.strip().upper(),
                segment=segment,
                block=block,
                id_attr=config.id_attr,
            )
        )

    return instruments, stats


def distance(a: Instrument, b: Instrument) -> float:
    return math.hypot(a.pos_x - b.pos_x, a.pos_y - b.pos_y)


def left_top_key(inst: Instrument) -> tuple[float, float, str, str]:
    # 最左上：X 越小越靠左；Y 越大越靠上。
    return inst.pos_x, -inst.pos_y, inst.type, inst.op


def nearest_neighbor_order(items: list[Instrument]) -> list[Instrument]:
    """
    组内编号顺序：
    1. 先找最左上的仪表；
    2. 再找距离当前仪表最近的同 OP 仪表；
    3. 循环直到该 OP 组编号完成。
    """
    if not items:
        return []

    remaining = list(items)
    current = min(remaining, key=left_top_key)
    ordered = [current]
    remaining.remove(current)

    while remaining:
        next_item = min(
            remaining,
            key=lambda inst: (
                distance(current, inst),
                inst.pos_x,
                -inst.pos_y,
                inst.type,
                inst.op,
            ),
        )
        ordered.append(next_item)
        remaining.remove(next_item)
        current = next_item

    return ordered


def ordered_ops_for_segment(items: list[Instrument]) -> list[str]:
    """
    OP 组顺序：
    不再使用 OP_ORDER，不再做前缀归并。
    每个 OP 按精确文本独立成组。
    各 OP 组之间按该组“最左上仪表”的位置排序。
    """
    ops = sorted({inst.op for inst in items})
    return sorted(
        ops,
        key=lambda op: left_top_key(
            min((inst for inst in items if inst.op == op), key=left_top_key)
        ),
    )


def format_pid_id(segment: int, serial: int) -> str:
    if segment < 1 or segment >= 10**SEGMENT_DIGITS:
        raise ValueError(f"工段号 {segment} 超出 {SEGMENT_DIGITS} 位编号范围")
    if serial < 1 or serial >= 10**SERIAL_DIGITS:
        raise ValueError(
            f"工段 {segment:0{SEGMENT_DIGITS}d} 的流水号 {serial} 超出 "
            f"{SERIAL_DIGITS} 位编号范围"
        )
    return f"{segment:0{SEGMENT_DIGITS}d}{serial:0{SERIAL_DIGITS}d}"


def build_numbering_plan(instruments: list[Instrument]) -> list[tuple[Instrument, str]]:
    """
    只保留 segment_op：
    每个“工段 + OP”独立从 1 编号。
    """
    plan: list[tuple[Instrument, str]] = []

    for segment in sorted({inst.segment for inst in instruments}):
        segment_items = [inst for inst in instruments if inst.segment == segment]

        for op in ordered_ops_for_segment(segment_items):
            op_items = [inst for inst in segment_items if inst.op == op]
            op_ordered = nearest_neighbor_order(op_items)

            for serial, inst in enumerate(op_ordered, start=1):
                plan.append((inst, format_pid_id(segment, serial)))

    return plan


def apply_numbering_plan(
    plan: list[tuple[Instrument, str]],
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    updated_count = 0
    failed_count = 0

    for inst, new_id in plan:
        old_id = inst.get_id()
        if dry_run:
            ok = True
        else:
            ok = inst.set_id(new_id)

        if ok:
            updated_count += 1
            if verbose:
                prefix = "[预览]" if dry_run else "[写入]"
                print(
                    f"{prefix} 工段 {inst.segment:02d} | OP={inst.op:<8} | "
                    f"{inst.type} @ ({inst.pos_x:.2f}, {inst.pos_y:.2f}) | "
                    f"{old_id!r} -> {new_id}"
                )
        else:
            failed_count += 1
            if verbose:
                print(
                    f"[失败] 工段 {inst.segment:02d} | OP={inst.op:<8} | "
                    f"{inst.type} @ ({inst.pos_x:.2f}, {inst.pos_y:.2f}) | "
                    f"无法写入属性 {inst.id_attr!r}"
                )

    return {
        "planned_count": len(plan),
        "updated_count": updated_count,
        "failed_count": failed_count,
    }


def summarize_instruments(instruments: list[Instrument]) -> None:
    print("\n扫描结果：")
    if not instruments:
        print("  未找到可编号的仪表块。")
        return

    for segment in sorted({inst.segment for inst in instruments}):
        segment_items = [inst for inst in instruments if inst.segment == segment]
        print(f"  工段 {segment:02d}: {len(segment_items)} 个")
        for op in ordered_ops_for_segment(segment_items):
            count = sum(1 for inst in segment_items if inst.op == op)
            print(f"    {op}: {count} 个")


def number_pid_instruments(
    dry_run: bool = False,
    save: bool = False,
    needle: str = TARGET_DWG_KEYWORD,
    path: str = TARGET_DWG_PATH,
    verbose: bool = True,
) -> dict[str, int]:
    config_map = build_config_map(BLOCK_CONFIG)

    _acad, document, _display_name = connect_document_from_rot(
        needle=needle,
        path=path,
        verbose=verbose,
    )

    all_blocks = collect_block_references_from_model_space(document, verbose=verbose)

    instruments, collect_stats = collect_instruments(
        all_blocks=all_blocks,
        config_map=config_map,
        segments=SEGMENTS,
        verbose=verbose,
    )

    if verbose:
        print(
            f"\n已扫描块参照 {collect_stats['block_refs']} 个；"
            f"匹配目标块 {collect_stats['matched_blocks']} 个；"
            f"可编号仪表 {len(instruments)} 个。"
        )
        print(
            f"跳过：无坐标 {collect_stats['skipped_no_point']}，"
            f"不在工段 {collect_stats['skipped_no_segment']}，"
            f"无 OP {collect_stats['skipped_no_op']}。"
        )
        summarize_instruments(instruments)
        if len(instruments) != 0:
            print("\n编号计划：")

    plan = build_numbering_plan(instruments)
    result = apply_numbering_plan(plan, dry_run=dry_run, verbose=verbose)

    if not dry_run:
        try:
            document.Regen(1)
        except Exception:
            pass
        if save:
            document.Save()

    summary = {
        **collect_stats,
        **result,
        "instrument_count": len(instruments),
    }

    print(
        "\n处理完成："
        f"计划编号 {summary['planned_count']} 个，"
        f"成功 {'预览' if dry_run else '写入'} {summary['updated_count']} 个，"
        f"失败 {summary['failed_count']} 个。"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="精简版 AutoCAD P&ID 自动仪表编号器")
    parser.add_argument(
        "--dry-run", action="store_true", help="只打印编号计划，不写入 AutoCAD。"
    )
    parser.add_argument(
        "--save", action="store_true", help="编号完成后保存 DWG。默认不自动保存。"
    )
    parser.add_argument(
        "--needle",
        default=TARGET_DWG_KEYWORD,
        help="ROT 中目标 DWG 路径/文件名关键词。",
    )
    parser.add_argument(
        "--path",
        default=TARGET_DWG_PATH,
        help="目标 DWG 完整路径；填写后优先按路径匹配。",
    )
    parser.add_argument("--quiet", action="store_true", help="减少输出。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    number_pid_instruments(
        dry_run=args.dry_run,
        save=args.save,
        needle=args.needle,
        path=args.path,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
