# -*- coding: utf-8 -*-
r"""ПРИЁМКА ОТКАЗА ПЕРЕНОСА: vnext/tools/sync-vnext-pair.py СНЯТ этапом Э4 (карточка #678, шаг Ш3).

Был строитель пары «рабочий каталог vnext-tools ↔ шаблон vnext/prototype»: переносил рабочий → шаблон
и намеренно не тянул обратно (замер 09.08: из четырнадцати перенесённых назад девять падали). С Э4 пакет —
единственный источник: vnext-tools контура — второй каталог установки update-tools.py, переноса
«контур → пакет» нет вовсе. Инструмент оставлен файлом и отказывает словами: вызов живёт в памяти ролей.
Прежние 26 случаев судили снятый код — он в истории пакета, последний commit с ним c4221fa.

Случаи и нарочные поломки — те же, что у отказа sync-to-template.py: функция judge приёмки
bite-transfer-roots.py (одна на два снятых инструмента — судить их порознь значило бы завести два
расходящихся описания одного отказа). Каталог-контроль ④ — vnext/prototype пакета, куда писал строитель.
⛔ Живой базы не касается; пакет только читается.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402

COMMON = HERE / "bite-transfer-roots.py"


def main() -> int:
    if not COMMON.is_file():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет общей части приёмки {COMMON} — отказ мерить, не «чисто»")
        return 2
    spec = importlib.util.spec_from_file_location("bite_transfer_refusal", COMMON)
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    return common.judge("vnext/tools/sync-vnext-pair.py", "vnext/prototype", "sync-vnext-pair.py")


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
