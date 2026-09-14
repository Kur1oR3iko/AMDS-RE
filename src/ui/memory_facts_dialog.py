"""重要事实表的查看和编辑界面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class MemoryFactsDialog(QDialog):
    def __init__(self, memory, parent=None):
        super().__init__(parent)
        self.memory = memory
        self._facts_by_id = {fact["id"]: fact for fact in memory.get_facts()}
        self.setWindowTitle("重要记忆")
        self.resize(760, 480)
        self.setMinimumSize(620, 380)

        layout = QVBoxLayout(self)
        tip = QLabel(
            "这些事实会比滚动摘要更优先地提供给模型。"
            "可直接修改类型和内容，空内容不会保存。"
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["类型", "内容", "来源"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        for fact in self._facts_by_id.values():
            self._append_row(fact)

        buttons = QHBoxLayout()
        add_button = QPushButton("添加")
        add_button.clicked.connect(self._add_row)
        buttons.addWidget(add_button)
        delete_button = QPushButton("删除选中")
        delete_button.clicked.connect(self._delete_selected)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        save_button = QPushButton("保存")
        save_button.clicked.connect(self._save)
        buttons.addWidget(save_button)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def _append_row(self, fact: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        category = QTableWidgetItem(str(fact.get("category", "其他")))
        category.setData(Qt.ItemDataRole.UserRole, str(fact.get("id", "")))
        self.table.setItem(row, 0, category)
        self.table.setItem(row, 1, QTableWidgetItem(str(fact.get("content", ""))))
        source = QTableWidgetItem(self._source_label(str(fact.get("source", "manual"))))
        source.setFlags(source.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 2, source)

    def _add_row(self):
        self._append_row({"category": "其他", "content": "", "source": "manual"})
        row = self.table.rowCount() - 1
        self.table.setCurrentCell(row, 1)
        self.table.editItem(self.table.item(row, 1))

    def _delete_selected(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.table.removeRow(row)

    def _save(self):
        facts = []
        for row in range(self.table.rowCount()):
            category_item = self.table.item(row, 0)
            content_item = self.table.item(row, 1)
            content = content_item.text().strip() if content_item else ""
            if not content:
                continue
            fact_id = str(category_item.data(Qt.ItemDataRole.UserRole) or "") if category_item else ""
            original = self._facts_by_id.get(fact_id, {})
            facts.append({
                **original,
                "id": fact_id,
                "category": category_item.text().strip() if category_item else "其他",
                "content": content,
                "source": original.get("source", "manual"),
            })
        try:
            self.memory.replace_facts(facts)
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.accept()

    @staticmethod
    def _source_label(source: str) -> str:
        return {"explicit": "用户要求", "auto": "自动提取", "manual": "手动添加"}.get(source, source)
