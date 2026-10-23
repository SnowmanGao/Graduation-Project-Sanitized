# Automation

入口为 `main.ipynb`，复杂逻辑下沉到 `core/`。

- `main.ipynb`: 交互入口
- `core/stream_pipeline.py`: Excel 提取、总表 CSV 导出、CAD CSV 模板填充
- `core/cad_applier.py`: AutoCAD 回填
- `core/paths.py`: 默认路径
- `map.json`: 流股编号映射
