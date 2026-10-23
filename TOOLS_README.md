# 化工毕业设计辅助工具链

本项目整理 Aspen 流股数据处理、AutoCAD 辅助操作、管道编号解析和管道选择相关工具，供学习和复用。

## 工具目录

| 目录 | 用途 |
| --- | --- |
| [Automation](./杂项/Automation/) | 从 Aspen 导出的 Excel 提取流股数据，生成 JSON、CSV，并辅助回填 CAD |
| [CadConnector](./杂项/CadConnector/) | 导出 CAD 文本、辅助 P&ID 仪表编号 |
| [CodexPipeParser](./杂项/CodexPipeParser/) | 浏览器中的管道编号解析器 |
| [PipeSelector](./杂项/PipeSelector/) | 管道选择、编号去重、汇总及选管 Skill 包 |

原项目非工具区域保留目录结构和文件名，文件内容全部清空为 0 字节；5 个含姓名或个人标识的文件名已改为中性名称。真正的空目录通过空的 `.gitkeep` 文件保留，克隆后仍可看到目录结构。AIGC 和存档汇总已移除，不提供占位文件。

空的 PDF、图片、Office 文档和工程文件仅用于展示结构，无法打开或执行。根 README 和已脱敏工具链保留实际内容。

## 使用说明

### 流股数据与 CAD 自动化

参考 [Automation 使用说明](./杂项/Automation/README.md)。该目录提供 Python 模块、Notebook 交互入口、依赖声明以及流股数据与映射配置。

Aspen 主工程及原始导出 Excel 未随本版本提供。运行完整流程前，需准备自己的输入文件并调整路径、流股映射及 CAD 模板。

### CAD 辅助操作

[仪表编号脚本](./杂项/CadConnector/pid_auto_numberer.py) 用于连接已打开的 AutoCAD 图纸并辅助编号。先根据自己的图纸调整匹配关键词、工段坐标、块名及属性标签，建议先使用 `--dry-run` 检查结果。

[文本导出脚本](./杂项/CadConnector/export_mtext_json.lsp) 用于辅助导出 CAD 文本信息。

### 管道编号解析

在浏览器中打开 [管道编号解析器](./杂项/CodexPipeParser/index.html)，并参考[编码说明](./杂项/CodexPipeParser/管道编号解析器.md)。

### 管道选择

[PipeSelector](./杂项/PipeSelector/) 包含标准管选择脚本、编号去重 Notebook、汇总数据、选管结果和可复用 Skill 压缩包。使用前应检查所采用的管径规格、设计流速、压力等级和手动覆盖配置是否适合自己的项目。

## 环境与限制

- Python 工具的依赖以各工具目录的说明和依赖声明为准。
- CAD COM 操作需要 Windows、AutoCAD 及相应 Python 依赖。
- 管道编号解析器可在浏览器中使用。
- Notebook 已清空执行输出；再次执行需要自行准备输入和软件环境。
- 保留的 BatchPlot.VLX 为编译工具，内部内容未完成全面审计。
- 工程参数和选管结果仅供学习参考，使用前应按实际工况及适用规范独立校核。

## Git 历史

本版本从原项目当前分支重建了 39 条空快照历史，作者与提交者统一为匿名 Contributor，保留原始提交时间与合并关系。随后提交当前脱敏工具链及本说明。

历史提交不包含原项目的文件树或文件内容，也未携带原仓库的远程配置。当前版本的文件仅出现在发布工具链的提交及其后续提交中。

本版本作为独立仓库 `Graduation-Project-Sanitized` 发布，不是原仓库的分支或 GitHub fork。仓库只包含重建的空快照历史、已脱敏工具链、说明文档和零字节占位文件；未导入原仓库的其他分支、标签或文件对象。原仓库不作修改。
