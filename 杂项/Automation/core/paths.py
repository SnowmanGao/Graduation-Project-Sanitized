from pathlib import Path


AUTOMATION_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = AUTOMATION_DIR.parent.parent

DEFAULT_XLSX_PATH = PROJECT_ROOT / "过程模拟" / "导出数据" / "PET_Flow.xlsx"
DEFAULT_MAP_PATH = AUTOMATION_DIR / "map.json"
DEFAULT_JSON_PATH = AUTOMATION_DIR / "output" / "aspen_stream.json"
DEFAULT_FULL_CSV_PATH = AUTOMATION_DIR / "output" / "aspen_stream.csv"
DEFAULT_SPLIT_CSV_DIR = PROJECT_ROOT / "过程模拟" / "导出数据"
