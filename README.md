# 实验记录中的样本处理事件与交接核对

本地文本工作区用于保存样本及批次实体识别相关的合成记录，并提供基础规范化和词项查看能力。

## 环境

需要 Python 3.11 或更新版本。运行程序仅使用 Python 标准库。测试依赖固定为 pytest 8.3.4，可执行 `python -m pip install -r requirements-dev.txt` 安装。

## 运行

运行 `PYTHONPATH=src python -m nlp_lab_sample_provenance.desk_cli` 查看归属核对报告：每次测量的实际批次与分装物、可用操作及原文依据、可合并的结果组、笔记与仪器时间的冲突，以及仍不能确定的点。`--notes` 指定笔记原文（默认 fixtures/records.json）。样例中的操作名称是资料登记标签。相同样本号可以出现在不同批次，归属按批次核对。纳入按测量实际发生时点核对，已签分析登记独立保留。

从项目根目录执行 `PYTHONPATH=src python -m nlp_lab_sample_provenance.cli ingest fixtures/records.json` 导入样例，随后执行 `PYTHONPATH=src python -m nlp_lab_sample_provenance.cli list` 查看记录。执行 `PYTHONPATH=src python -m nlp_lab_sample_provenance.cli notes` 查看从笔记识别出的样本、分装关系、交接事件和相对时间（可用 `--source` 按来源筛选）。工作数据写入 `var/records.json`。业务查询使用 fixtures/business.json 中的初始资料，约定见 fixtures/business-contract.md。执行 PYTHONPATH=src python -m nlp_lab_sample_provenance.cli business 可查看当前业务目录结果。

样例为本地合成文本。记录包含来源、修订号和原文，当前工作区对空白做统一处理，并提供字符及英文词项切分。

## 测试

执行 `python -m pytest -q` 检查规范化、记录持久化、来源筛选、笔记识别和归属核对。
